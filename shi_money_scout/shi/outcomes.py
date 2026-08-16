import hashlib
import json
from pathlib import Path
from typing import Any


STAGE_SCORES = {
    "surfaced": 0.05,
    "pursued": 0.15,
    "response": 0.35,
    "interview": 0.50,
    "proposal": 0.65,
    "offer": 0.85,
    "paid": 1.00,
    "rejected": 0.00,
    "ignored": 0.00,
}


def opportunity_id(url: str) -> str:
    return hashlib.sha256((url or "").strip().encode("utf-8")).hexdigest()[:16]


def load_outcomes(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def save_outcomes(path: Path, outcomes: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(outcomes, indent=2, sort_keys=True))


def normalize_stage(stage: str) -> str:
    value = (stage or "").strip().lower()
    if value not in STAGE_SCORES:
        raise ValueError(f"Unknown outcome stage: {stage}")
    return value


def record_outcome(path: Path, url: str, stage: str, amount: float | None = None, notes: str = "") -> dict[str, Any]:
    stage = normalize_stage(stage)
    outcomes = load_outcomes(path)
    oid = opportunity_id(url)
    row = outcomes.get(oid, {})
    row.update({
        "opportunity_id": oid,
        "url": url,
        "stage": stage,
        "outcome_score": STAGE_SCORES[stage],
        "notes": notes,
    })
    if amount is not None:
        row["amount"] = float(amount)
    outcomes[oid] = row
    save_outcomes(path, outcomes)
    return row


def attach_outcome(candidate: dict[str, Any], outcomes: dict[str, Any]) -> dict[str, Any]:
    oid = opportunity_id(candidate.get("url", ""))
    return outcomes.get(oid, {})
