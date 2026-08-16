import json
import re
import requests

SYSTEM = """You are one reviewer in an opportunity-screening committee.
Evaluate only the evidence supplied. Do not invent facts, companies, compensation,
deadlines, contacts, or requirements.

Return ONLY valid JSON with this schema:
{
  "buyer_intent": 0-10,
  "revenue_potential": 0-10,
  "skill_fit": 0-10,
  "visible_pain": 0-10,
  "urgency": 0-10,
  "decision_maker_access": 0-10,
  "time_to_first_dollar": 0-10,
  "acquisition_friction": 0-10,
  "competition": 0-10,
  "reality_confidence": 0-10,
  "fatal_flaws": ["..."],
  "evidence": ["short evidence snippets from supplied text only"],
  "verdict": "pursue|maybe|reject"
}

For acquisition_friction, a HIGH score means LOW friction/easier acquisition.
For competition, a HIGH score means MORE favorable/lower competitive difficulty.
"""

def _extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise

def review_with_ollama(model, candidate, text, profile, ollama_url, timeout=90):
    prompt = {
        "opportunity": candidate,
        "profile": profile,
        "page_text": text[:12000],
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(prompt)}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0}
    }
    r = requests.post(
        f"{ollama_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout
    )
    r.raise_for_status()
    body = r.json()
    return _extract_json(body["message"]["content"])
