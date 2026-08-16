from ddgs import DDGS

def search_web(queries, max_results_per_query=8):
    seen = set()
    results = []
    with DDGS() as ddgs:
        for q in queries:
            try:
                for item in ddgs.text(q, max_results=max_results_per_query):
                    url = item.get("href") or item.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    results.append({
                        "query": q,
                        "title": item.get("title", ""),
                        "url": url,
                        "snippet": item.get("body", "") or item.get("snippet", "")
                    })
            except Exception as e:
                results.append({
                    "query": q,
                    "title": "",
                    "url": "",
                    "snippet": "",
                    "search_error": str(e)
                })
    return results
