import json
from collections import Counter
from statistics import median, pstdev

NUMERIC_KEYS = [
    "buyer_intent",
    "revenue_potential",
    "skill_fit",
    "visible_pain",
    "urgency",
    "decision_maker_access",
    "time_to_first_dollar",
    "acquisition_friction",
    "competition",
    "reality_confidence",
]


def _clamp(value, lo=0.0, hi=10.0):
    return max(lo, min(hi, value))


def _norm_verdict(raw):
    if not raw:
        return ""
    v = str(raw).strip().lower()
    if v in {"pursue", "maybe", "reject"}:
        return v
    if "reject" in v:
        return "reject"
    if "pursue" in v or "go" in v:
        return "pursue"
    if "maybe" in v or "hold" in v:
        return "maybe"
    return ""


def _dedupe_evidence(items):
    seen = set()
    out = []
    for item in items:
        if isinstance(item, dict):
            key = json.dumps(item, sort_keys=True)
        else:
            key = str(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


class ConsensusAgent:
    def __init__(self, config=None):
        cfg = config or {}
        self.strategy = str(cfg.get("strategy", "median")).strip().lower()
        self.min_reviewers = max(1, int(cfg.get("min_reviewers", 1)))
        self.trim_ratio = _clamp(float(cfg.get("trim_ratio", 0.2)), 0.0, 0.45)
        self.disagreement_penalty = cfg.get("disagreement_penalty", {}) or {}
        self.evidence_penalty = cfg.get("evidence_penalty", {}) or {}
        self.use_model_weights = bool(cfg.get("use_model_weights", False))
        self.model_weights = cfg.get("model_weights", {}) or {}

    def _weight_for(self, review):
        if not self.use_model_weights:
            return 1.0
        model_name = str(review.get("_model", "")).strip()
        try:
            return max(0.0, float(self.model_weights.get(model_name, 1.0)))
        except Exception:
            return 1.0

    def _weighted_mean(self, value_weight_pairs):
        total_w = sum(w for _, w in value_weight_pairs)
        if total_w <= 0:
            return 0.0
        return sum(v * w for v, w in value_weight_pairs) / total_w

    def _weighted_median(self, value_weight_pairs):
        ordered = sorted(value_weight_pairs, key=lambda x: x[0])
        total_w = sum(w for _, w in ordered)
        if total_w <= 0:
            return median([v for v, _ in ordered])
        threshold = total_w / 2.0
        running = 0.0
        for v, w in ordered:
            running += w
            if running >= threshold:
                return v
        return ordered[-1][0]

    def _aggregate(self, value_weight_pairs):
        if not value_weight_pairs:
            return 0.0
        if self.strategy == "trimmed_mean" and len(value_weight_pairs) >= 3:
            ordered = sorted(value_weight_pairs, key=lambda x: x[0])
            cut = int(len(ordered) * self.trim_ratio)
            if cut > 0 and (2 * cut) < len(ordered):
                ordered = ordered[cut:-cut]
            return self._weighted_mean(ordered)
        if self.strategy == "mean":
            return self._weighted_mean(value_weight_pairs)
        return self._weighted_median(value_weight_pairs)

    def _stddev_by_key(self, good):
        out = {}
        for key in NUMERIC_KEYS:
            vals = []
            for r in good:
                try:
                    vals.append(float(r.get(key, 0)))
                except Exception:
                    continue
            if len(vals) >= 2:
                out[key] = round(pstdev(vals), 3)
        return out

    def combine(self, reviews):
        good = [r for r in reviews if isinstance(r, dict) and not r.get("_error")]
        bad = [r for r in reviews if isinstance(r, dict) and r.get("_error")]

        if len(good) < self.min_reviewers:
            return {
                "available": False,
                "reason": "insufficient_valid_reviews",
                "required_reviews": self.min_reviewers,
                "received_reviews": len(good),
                "scores": {},
                "fatal_flaws": [],
                "evidence": [],
                "verdicts": [],
                "verdict_counts": {},
                "majority_verdict": "",
                "disagreement": {},
                "evidence_quality": {},
                "score_penalty": 0.0,
                "errors": [str(x.get("_error")) for x in bad if x.get("_error")],
            }

        scores = {}
        for key in NUMERIC_KEYS:
            vals = []
            for r in good:
                try:
                    vals.append((float(r.get(key, 0)), self._weight_for(r)))
                except Exception:
                    continue
            if vals:
                scores[key] = round(_clamp(self._aggregate(vals)), 2)

        flaws = []
        evidence = []
        verdicts = []
        verification_ratios = []
        for r in good:
            flaws.extend(r.get("fatal_flaws", []) or [])
            evidence.extend(r.get("evidence", []) or [])
            verdict = _norm_verdict(r.get("verdict"))
            if verdict:
                verdicts.append(verdict)
            try:
                verification_ratios.append(float(r.get("evidence_verification_ratio", 0.0)))
            except Exception:
                pass

        verdict_counts = dict(Counter(verdicts))
        majority_verdict = ""
        if verdict_counts:
            majority_verdict = max(sorted(verdict_counts), key=lambda x: verdict_counts[x])

        disagreement = {
            "stddev_by_signal": self._stddev_by_key(good),
            "verdict_fragmentation": round(len(verdict_counts) / 3.0, 3) if verdict_counts else 0.0,
        }
        evidence_quality = {
            "mean_verification_ratio": round(sum(verification_ratios) / len(verification_ratios), 3)
            if verification_ratios else 0.0,
            "verified_items": sum(int(r.get("evidence_verified_count", 0) or 0) for r in good),
            "submitted_items": sum(int(r.get("evidence_total_count", 0) or 0) for r in good),
        }

        score_penalty = 0.0
        if self.disagreement_penalty.get("enabled", True):
            stddev_threshold = float(self.disagreement_penalty.get("stddev_threshold", 2.0))
            max_penalty = float(self.disagreement_penalty.get("max_penalty_points", 10.0))
            high_var = [v for v in disagreement["stddev_by_signal"].values() if v >= stddev_threshold]
            if high_var:
                scale = min(1.0, len(high_var) / max(1, len(NUMERIC_KEYS) // 2))
                score_penalty += max_penalty * scale

        if self.evidence_penalty.get("enabled", True) and evidence_quality["submitted_items"]:
            min_ratio = float(self.evidence_penalty.get("min_verification_ratio", 0.6))
            max_penalty = float(self.evidence_penalty.get("max_penalty_points", 8.0))
            ratio = evidence_quality["mean_verification_ratio"]
            if ratio < min_ratio:
                deficit = (min_ratio - ratio) / max(min_ratio, 0.001)
                score_penalty += max_penalty * min(1.0, deficit)

        return {
            "available": True,
            "scores": scores,
            "fatal_flaws": sorted(set(map(str, flaws))),
            "evidence": _dedupe_evidence(evidence)[:12],
            "verdicts": verdicts,
            "verdict_counts": verdict_counts,
            "majority_verdict": majority_verdict,
            "disagreement": disagreement,
            "evidence_quality": evidence_quality,
            "score_penalty": round(score_penalty, 2),
            "model_weights_used": {
                str(r.get("_model", "unknown")): self._weight_for(r) for r in good
            } if self.use_model_weights else {},
            "errors": [str(x.get("_error")) for x in bad if x.get("_error")],
        }


def combine_reviews(reviews, config=None):
    return ConsensusAgent(config=config).combine(reviews)
