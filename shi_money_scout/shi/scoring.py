import re

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


def deterministic_signals(candidate, text, profile, evidence=None):
    evidence = evidence or {}
    title_snippet = (candidate.get("title", "") + "\n" + candidate.get("snippet", "")).lower()
    hay = (title_snippet + "\n" + (text or "")).lower()
    skills = profile.get("skills", [])

    skill_hits = sum(1 for s in skills if s.lower() in hay)
    skill_fit = clamp(skill_hits * 1.4)

    # Prefer explicit, extracted buyer signals over generic keyword occurrence in page boilerplate.
    explicit_buyer = len(evidence.get("buyer_intent", []) or [])
    title_buyer_words = ["hiring", "contract", "contractor", "rfp", "consultant", "job", "opening"]
    title_buyer_hits = sum(1 for w in title_buyer_words if w in title_snippet)
    buyer_intent = clamp(explicit_buyer * 1.8 + title_buyer_hits * 1.2)

    comp_evidence = evidence.get("compensation", []) or []
    money_patterns = [r"budget", r"compensation", r"salary", r"pay range"]
    generic_money_hits = sum(1 for p in money_patterns if re.search(p, hay, re.I))
    revenue_potential = clamp(2 + len(comp_evidence) * 2.5 + generic_money_hits)

    pain_words = [
        "migration", "manual", "modernize", "replace", "issue", "problem",
        "remediate", "integration", "reporting", "dashboard", "automation",
    ]
    visible_pain = clamp(sum(1.0 for w in pain_words if w in hay))

    urgency = clamp(len(evidence.get("urgency", []) or []) * 2.0)
    if evidence.get("duration"):
        urgency = clamp(urgency + 1.0)

    decision_maker_access = clamp(len(evidence.get("access", []) or []) * 1.5)

    low_friction_words = ["apply", "remote", "contract", "subcontractor", "rfp", "proposal"]
    high_friction_words = ["cold call", "commission only", "door to door"]
    acquisition_friction = 6
    acquisition_friction += sum(0.7 for w in low_friction_words if w in hay)
    acquisition_friction -= sum(2 for w in high_friction_words if w in hay)
    if evidence.get("remote"):
        acquisition_friction += 0.5
    acquisition_friction = clamp(acquisition_friction)

    time_to_first_dollar = clamp(3 + urgency * 0.5 + buyer_intent * 0.35)

    competition = 5
    if "senior" in title_snippet or "architect" in title_snippet:
        competition -= 1
    if "0-2 years" in hay or "entry level" in hay:
        competition -= 1
    competition = clamp(competition)

    reality_confidence = 1
    if candidate.get("url"):
        reality_confidence += 2
    if evidence.get("text_available"):
        reality_confidence += 2
    if explicit_buyer:
        reality_confidence += 2
    if comp_evidence or evidence.get("duration"):
        reality_confidence += 1
    if evidence.get("access"):
        reality_confidence += 1
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
    hay = (candidate.get("title", "") + "\n" + candidate.get("snippet", "") + "\n" + (text or "")).lower()
    reasons = []
    for phrase in profile.get("avoid", []):
        if phrase.lower() in hay:
            reasons.append(f"contains avoid phrase: {phrase}")
    if not candidate.get("url"):
        reasons.append("no verifiable URL")
    return reasons
