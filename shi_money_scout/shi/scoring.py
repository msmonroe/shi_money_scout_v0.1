import re
from datetime import datetime, timezone

CRITERIA = [
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

def clamp(v, lo=0, hi=10):
    return max(lo, min(hi, v))

def deterministic_signals(candidate, text, profile):
    hay = (candidate.get("title","") + "\n" + candidate.get("snippet","") + "\n" + text).lower()
    skills = profile.get("skills", [])

    skill_hits = sum(1 for s in skills if s.lower() in hay)
    skill_fit = clamp(skill_hits * 1.4)

    buyer_words = [
        "hiring", "contract", "contractor", "request for proposal", "rfp",
        "seeking", "looking for", "consultant", "apply", "opening", "job"
    ]
    buyer_intent = clamp(sum(1.4 for w in buyer_words if w in hay))

    money_patterns = [
        r"\$\s?\d{2,3}(?:\.\d+)?\s*/\s*(?:hr|hour)",
        r"\$\s?\d{1,3}(?:,\d{3})+",
        r"budget",
        r"compensation",
        r"salary",
        r"pay range",
    ]
    money_hits = sum(1 for p in money_patterns if re.search(p, hay, re.I))
    revenue_potential = clamp(3 + money_hits * 2)

    pain_words = ["migration", "manual", "modernize", "replace", "issue", "problem",
                  "remediate", "integration", "reporting", "dashboard", "automation"]
    visible_pain = clamp(sum(1.0 for w in pain_words if w in hay))

    urgency_words = ["immediate", "urgent", "asap", "start date", "6 month", "12 month",
                     "contract", "opening", "deadline", "due date"]
    urgency = clamp(sum(1.2 for w in urgency_words if w in hay))

    access_words = ["recruiter", "hiring manager", "contact", "email", "apply", "proposal"]
    decision_maker_access = clamp(sum(1.2 for w in access_words if w in hay))

    low_friction_words = ["apply", "remote", "contract", "subcontractor", "rfp", "proposal"]
    high_friction_words = ["cold call", "commission only", "door to door"]
    acquisition_friction = 7
    acquisition_friction += sum(0.7 for w in low_friction_words if w in hay)
    acquisition_friction -= sum(2 for w in high_friction_words if w in hay)
    acquisition_friction = clamp(acquisition_friction)

    time_to_first_dollar = clamp(4 + urgency * 0.5 + buyer_intent * 0.3)

    competition = 5
    if "senior" in hay or "architect" in hay:
        competition -= 1
    if "0-2 years" in hay or "entry level" in hay:
        competition -= 1
    competition = clamp(competition)

    reality_confidence = 2
    if candidate.get("url"):
        reality_confidence += 2
    if text:
        reality_confidence += 3
    if any(w in hay for w in ["apply", "deadline", "salary", "contract", "rfp"]):
        reality_confidence += 2
    reality_confidence = clamp(reality_confidence)

    return {
        "buyer_intent": buyer_intent,
        "revenue_potential": revenue_potential,
        "skill_fit": skill_fit,
        "visible_pain": visible_pain,
        "urgency": urgency,
        "decision_maker_access": decision_maker_access,
        "time_to_first_dollar": time_to_first_dollar,
        "acquisition_friction": acquisition_friction,
        "competition": competition,
        "reality_confidence": reality_confidence,
    }

def weighted_score(signals, weights):
    total_weight = sum(weights.get(k, 1.0) for k in CRITERIA)
    raw = sum(signals.get(k, 0) * weights.get(k, 1.0) for k in CRITERIA)
    return round((raw / (10 * total_weight)) * 100, 1)

def hard_reject(candidate, text, profile):
    hay = (candidate.get("title","") + "\n" + candidate.get("snippet","") + "\n" + text).lower()
    reasons = []
    for phrase in profile.get("avoid", []):
        if phrase.lower() in hay:
            reasons.append(f"contains avoid phrase: {phrase}")
    if not candidate.get("url"):
        reasons.append("no verifiable URL")
    return reasons
