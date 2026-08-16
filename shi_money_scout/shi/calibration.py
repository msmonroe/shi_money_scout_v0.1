import json
from pathlib import Path
from statistics import median

from shi.consensus import NUMERIC_KEYS


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _read_history(path):
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text())
    except Exception:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("opportunities"), list):
        return obj["opportunities"]
    return []


def _pick_target_scores(opportunity, target_key):
    target = opportunity.get(target_key, {})
    if isinstance(target, dict):
        return target
    return {}


def _derive_weights_from_history(
    history,
    target_key,
    min_samples,
    min_weight,
    max_weight,
    smooth_to,
    alpha,
):
    model_errors = {}

    for opp in history:
        target_scores = _pick_target_scores(opp, target_key)
        if not target_scores:
            continue

        for review in opp.get("model_reviews", []):
            if not isinstance(review, dict) or review.get("_error"):
                continue
            model_name = str(review.get("_model", "")).strip()
            if not model_name:
                continue

            diffs = []
            for key in NUMERIC_KEYS:
                tv = _to_float(target_scores.get(key))
                rv = _to_float(review.get(key))
                if tv is None or rv is None:
                    continue
                diffs.append(abs(tv - rv))

            if not diffs:
                continue

            review_mae = sum(diffs) / len(diffs)
            stats = model_errors.setdefault(model_name, {"sum_mae": 0.0, "samples": 0})
            stats["sum_mae"] += review_mae
            stats["samples"] += 1

    eligible = {
        model: data
        for model, data in model_errors.items()
        if data["samples"] >= min_samples
    }

    if not eligible:
        return {}, model_errors

    raw_reliability = {}
    for model, data in eligible.items():
        mae = data["sum_mae"] / max(1, data["samples"])
        # Lower MAE means higher reliability.
        raw_reliability[model] = 1.0 / (0.25 + mae)

    baseline = median(raw_reliability.values()) if raw_reliability else 1.0
    baseline = baseline if baseline > 0 else 1.0

    weights = {}
    for model, rel in raw_reliability.items():
        normalized = rel / baseline
        smoothed = smooth_to + alpha * (normalized - smooth_to)
        weights[model] = round(_clamp(smoothed, min_weight, max_weight), 3)

    return weights, model_errors


def run_auto_calibration(consensus_cfg, root_dir):
    auto_cfg = (consensus_cfg or {}).get("auto_calibration", {}) or {}
    enabled = bool(auto_cfg.get("enabled", False))
    if not enabled:
        return {
            "enabled": False,
            "applied": False,
            "weights": {},
            "reason": "disabled",
        }

    history_file = auto_cfg.get("history_file", "output/opportunities.json")
    target_key = str(auto_cfg.get("target", "deterministic_scores")).strip()
    min_samples = int(auto_cfg.get("min_samples_per_model", 8))
    min_weight = float(auto_cfg.get("min_weight", 0.6))
    max_weight = float(auto_cfg.get("max_weight", 1.6))
    smooth_to = float(auto_cfg.get("smooth_to", 1.0))
    alpha = float(auto_cfg.get("alpha", 0.5))
    apply_to_runtime = bool(auto_cfg.get("apply_to_runtime", True))

    history_path = Path(root_dir) / history_file
    history = _read_history(history_path)

    weights, model_errors = _derive_weights_from_history(
        history=history,
        target_key=target_key,
        min_samples=max(1, min_samples),
        min_weight=min_weight,
        max_weight=max_weight,
        smooth_to=smooth_to,
        alpha=_clamp(alpha, 0.0, 1.0),
    )

    result = {
        "enabled": True,
        "applied": bool(weights) and apply_to_runtime,
        "weights": weights,
        "history_file": str(history_file),
        "history_rows": len(history),
        "target": target_key,
        "min_samples_per_model": min_samples,
        "model_errors": model_errors,
        "reason": "ok" if weights else "insufficient_history",
    }

    suggestions_file = auto_cfg.get("write_suggestions_file", "output/model_weights.suggested.json")
    if suggestions_file:
        out_path = Path(root_dir) / suggestions_file
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        result["suggestions_file"] = str(suggestions_file)

    return result
