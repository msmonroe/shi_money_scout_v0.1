from pathlib import Path
import json
import time
import yaml

from shi.search import search_web
from shi.fetch import fetch_text
from shi.scoring import deterministic_signals, weighted_score, hard_reject
from shi.models import review_with_ollama
from shi.consensus import ConsensusAgent
from shi.calibration import run_auto_calibration

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "config.yaml"
OUT = ROOT / "output"
STATUS = OUT / "status.json"


def _fmt_duration(seconds):
    seconds = int(max(0, seconds))
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    if hrs:
        return f"{hrs}h {mins}m {sec}s"
    if mins:
        return f"{mins}m {sec}s"
    return f"{sec}s"


def _log_status(message):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def _write_status(payload):
    STATUS.write_text(json.dumps(payload, indent=2))

def load_config():
    if not CFG.exists():
        raise SystemExit("Missing config.yaml. Copy config.example.yaml to config.yaml first.")
    return yaml.safe_load(CFG.read_text())

def blend(det, consensus_scores):
    if not consensus_scores:
        return det
    out = {}
    for k, v in det.items():
        # Deterministic evidence has majority control.
        out[k] = round(v * 0.65 + consensus_scores.get(k, v) * 0.35, 2)
    return out

def main():
    run_start = time.time()
    _log_status("Loading configuration")
    cfg = load_config()
    OUT.mkdir(exist_ok=True)

    status = {
        "phase": "initializing",
        "started_at_unix": int(run_start),
        "total_candidates": 0,
        "processed_candidates": 0,
        "current_index": 0,
        "current_url": "",
        "elapsed_seconds": 0,
        "eta_seconds": 0,
        "complete": False,
    }
    _write_status(status)

    consensus_cfg = dict(cfg.get("models", {}).get("consensus", {}) or {})
    calibration = run_auto_calibration(consensus_cfg, ROOT)
    if calibration.get("applied"):
        merged = dict(consensus_cfg.get("model_weights", {}) or {})
        merged.update(calibration.get("weights", {}))
        consensus_cfg["use_model_weights"] = True
        consensus_cfg["model_weights"] = merged
    consensus_agent = ConsensusAgent(consensus_cfg)

    _log_status("Searching web for candidates")
    candidates = search_web(
        cfg["search"]["queries"],
        cfg["search"].get("max_results_per_query", 8)
    )
    total = len(candidates)
    _log_status(f"Found {total} candidates. Starting evaluation")
    status["phase"] = "evaluating"
    status["total_candidates"] = total
    _write_status(status)

    ranked = []
    for idx, c in enumerate(candidates, 1):
        item_start = time.time()
        status["current_index"] = idx
        status["current_url"] = c.get("url", "")
        _write_status(status)

        if not c.get("url"):
            _log_status(f"[{idx}/{total}] Skipping candidate with no URL")
            continue

        _log_status(f"[{idx}/{total}] Fetching page text")

        fetched = fetch_text(c["url"])
        text = fetched.get("text", "") if fetched.get("ok") else ""

        reject_reasons = hard_reject(c, text, cfg["profile"])
        det = deterministic_signals(c, text, cfg["profile"])

        reviews = []
        if cfg.get("models", {}).get("enabled", False):
            model_list = cfg["models"].get("reviewers", [])
            for model_idx, model in enumerate(model_list, 1):
                _log_status(f"[{idx}/{total}] Model {model_idx}/{len(model_list)}: {model}")
                try:
                    r = review_with_ollama(
                        model=model,
                        candidate=c,
                        text=text,
                        profile=cfg["profile"],
                        ollama_url=cfg["models"]["ollama_url"],
                        timeout=cfg["models"].get("timeout_seconds", 90),
                    )
                    r["_model"] = model
                    reviews.append(r)
                except Exception as e:
                    reviews.append({"_model": model, "_error": str(e)})

        consensus = consensus_agent.combine(reviews)
        final_signals = blend(det, consensus.get("scores", {}))
        score = weighted_score(final_signals, cfg["scoring"]["weights"])
        score = max(0.0, round(score - float(consensus.get("score_penalty", 0.0)), 1))

        # Strong penalty for hard rejects.
        if reject_reasons:
            score = min(score, 25)

        if consensus.get("majority_verdict") == "reject":
            score = min(score, 40)

        ranked.append({
            **c,
            "fetch_ok": fetched.get("ok", False),
            "fetch_error": fetched.get("error", ""),
            "hard_reject_reasons": reject_reasons,
            "deterministic_scores": det,
            "model_reviews": reviews,
            "consensus": consensus,
            "final_scores": final_signals,
            "score": score,
        })

        elapsed = time.time() - run_start
        avg_per_item = elapsed / idx
        eta = avg_per_item * max(0, total - idx)
        status["processed_candidates"] = idx
        status["elapsed_seconds"] = int(elapsed)
        status["eta_seconds"] = int(eta)
        _write_status(status)
        _log_status(
            f"[{idx}/{total}] Complete in {_fmt_duration(time.time() - item_start)} | "
            f"Elapsed {_fmt_duration(elapsed)} | ETA {_fmt_duration(eta)}"
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    threshold = cfg["scoring"].get("minimum_score_to_surface", 62)
    surfaced = [r for r in ranked if r["score"] >= threshold and not r["hard_reject_reasons"]]

    (OUT / "opportunities.json").write_text(json.dumps(ranked, indent=2))

    lines = ["# Shi Money Scout Report", ""]
    if calibration.get("enabled"):
        lines.append("## Calibration")
        lines.append(f"- history: {calibration.get('history_file','')}")
        lines.append(f"- target: {calibration.get('target','')}")
        lines.append(f"- rows analyzed: {calibration.get('history_rows', 0)}")
        lines.append(f"- applied at runtime: {calibration.get('applied', False)}")
        if calibration.get("weights"):
            lines.append("- suggested weights:")
            for model, weight in sorted(calibration["weights"].items()):
                lines.append(f"  - {model}: {weight}")
        else:
            lines.append(f"- status: {calibration.get('reason', 'insufficient_history')}")
        lines.append("")

    if not surfaced:
        lines += ["No opportunities cleared the current threshold.", ""]
    for i, r in enumerate(surfaced[:20], 1):
        lines += [
            f"## {i}. {r['title'] or '(untitled)'}",
            f"**Score:** {r['score']}/100",
            f"**URL:** {r['url']}",
            f"**Found via:** `{r['query']}`",
            "",
            f"**Snippet:** {r.get('snippet','')}",
            "",
            "**Final criteria:**",
        ]
        for k, v in r["final_scores"].items():
            lines.append(f"- {k}: {v}/10")
        if r["consensus"].get("majority_verdict"):
            lines.append(f"- consensus verdict: {r['consensus']['majority_verdict']}")
        if r["consensus"].get("score_penalty"):
            lines.append(f"- disagreement penalty: -{r['consensus']['score_penalty']} points")
        if r["consensus"].get("fatal_flaws"):
            lines += ["", "**Model concerns:**"] + [
                f"- {x}" for x in r["consensus"]["fatal_flaws"]
            ]
        lines.append("")

    (OUT / "report.md").write_text("\n".join(lines))

    status["phase"] = "complete"
    status["complete"] = True
    status["elapsed_seconds"] = int(time.time() - run_start)
    status["eta_seconds"] = 0
    _write_status(status)

    print(f"Scanned {len(ranked)} candidates.")
    print(f"Surfaced {len(surfaced)} opportunities >= {threshold}.")
    print(f"Report: {OUT / 'report.md'}")

if __name__ == "__main__":
    main()
