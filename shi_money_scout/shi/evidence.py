import re
from typing import Any


_COMP_PATTERNS = [
    re.compile(r"\$\s?\d{2,3}(?:\.\d+)?\s*(?:-|–|to)\s*\$?\s?\d{2,3}(?:\.\d+)?\s*/\s*(?:hr|hour)", re.I),
    re.compile(r"\$\s?\d{2,3}(?:\.\d+)?\s*/\s*(?:hr|hour)", re.I),
    re.compile(r"\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?", re.I),
]

_DURATION_PATTERNS = [
    re.compile(r"\b\d+\s*(?:month|months|mo)\b", re.I),
    re.compile(r"\b\d+\s*(?:week|weeks|wk)\b", re.I),
    re.compile(r"\bcontract[- ]to[- ]hire\b", re.I),
]


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()


def _snippet(text: str, start: int, end: int, radius: int = 100) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return " ".join(text[lo:hi].split())


def _first_matches(text: str, patterns, limit: int = 6):
    out = []
    seen = set()
    for pattern in patterns:
        for match in pattern.finditer(text or ""):
            value = match.group(0).strip()
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "value": value,
                "quote": _snippet(text, match.start(), match.end()),
                "offset": match.start(),
            })
            if len(out) >= limit:
                return out
    return out


def extract_evidence(candidate: dict[str, Any], text: str) -> dict[str, Any]:
    """Extract auditable, deterministic evidence from a fetched opportunity page."""
    hay = text or ""
    lower = hay.lower()

    buyer_terms = [
        "apply now", "submit proposal", "request for proposal", "rfp", "we are hiring",
        "we're hiring", "seeking", "looking for", "contractor", "consultant", "job opening",
    ]
    urgency_terms = ["urgent", "immediate", "asap", "start date", "deadline", "due date"]
    access_terms = ["apply", "contact", "recruiter", "hiring manager", "submit proposal", "email"]

    def term_quotes(terms, limit=6):
        rows = []
        for term in terms:
            pos = lower.find(term)
            if pos >= 0:
                rows.append({
                    "value": term,
                    "quote": _snippet(hay, pos, pos + len(term)),
                    "offset": pos,
                })
            if len(rows) >= limit:
                break
        return rows

    return {
        "source_url": candidate.get("url", ""),
        "compensation": _first_matches(hay, _COMP_PATTERNS),
        "duration": _first_matches(hay, _DURATION_PATTERNS),
        "buyer_intent": term_quotes(buyer_terms),
        "urgency": term_quotes(urgency_terms),
        "access": term_quotes(access_terms),
        "remote": "remote" in lower,
        "text_available": bool(hay.strip()),
    }


def verify_review_evidence(review: dict[str, Any], page_text: str) -> dict[str, Any]:
    """Verify reviewer evidence against the supplied page text.

    Reviewers should return evidence as [{"claim": "...", "quote": "..."}].
    Only quotes that actually occur in the fetched page are retained as verified.
    """
    supplied = review.get("evidence", []) or []
    normalized_page = _norm(page_text)
    verified = []
    rejected = []

    for item in supplied:
        if isinstance(item, dict):
            quote = str(item.get("quote", "")).strip()
            claim = str(item.get("claim", "")).strip()
        else:
            quote = str(item).strip()
            claim = ""

        if not quote:
            rejected.append({"claim": claim, "quote": quote, "reason": "missing_quote"})
            continue

        nq = _norm(quote)
        if nq and nq in normalized_page:
            verified.append({"claim": claim, "quote": quote})
        else:
            rejected.append({"claim": claim, "quote": quote, "reason": "quote_not_found"})

    total = len(supplied)
    ratio = (len(verified) / total) if total else 0.0
    out = dict(review)
    out["evidence"] = verified
    out["evidence_rejected"] = rejected
    out["evidence_verification_ratio"] = round(ratio, 3)
    out["evidence_verified_count"] = len(verified)
    out["evidence_total_count"] = total
    return out
