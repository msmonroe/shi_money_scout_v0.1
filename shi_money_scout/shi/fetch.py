import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShiMoneyScout/0.1; +local-research)"
}

def fetch_text(url, timeout=15, max_chars=18000):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype:
            return {"ok": False, "text": "", "error": f"unsupported content-type: {ctype}"}
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = "\n".join(
            line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
        )
        return {"ok": True, "text": text[:max_chars], "error": ""}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e)}
