"""Query the deployed search stack and write data.json for GitHub Pages.

Environment variables:
  FIRECRAWL_URL   public Codespace URL of the Firecrawl API, e.g. https://xxx-3002.app.github.dev
  SEARXNG_URL     public Codespace URL of SearXNG, e.g. https://xxx-8080.app.github.dev
  SEARCH_QUERIES  comma separated queries (default: a small general-purpose set)
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request

FIRECRAWL_URL = os.environ.get("FIRECRAWL_URL", "").rstrip("/")
SEARXNG_URL = os.environ.get("SEARXNG_URL", "").rstrip("/")
QUERIES = [
    q.strip()
    for q in os.environ.get(
        "SEARCH_QUERIES",
        "searxng json api,firecrawl self host,llm web search",
    ).split(",")
    if q.strip()
]


def post_json(url, payload, timeout=90):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def get_json(url, timeout=90):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def main():
    out = {
        "schema": "llm-search-api/v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generated_at_cst": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).isoformat(),
        "schedule": "daily 09:00-11:00 Asia/Shanghai",
        "sources": {"firecrawl": FIRECRAWL_URL, "searxng": SEARXNG_URL},
        "queries": QUERIES,
        "results": [],
        "errors": [],
    }

    for query in QUERIES:
        item = {"query": query, "firecrawl": None, "searxng": None}
        if FIRECRAWL_URL:
            try:
                item["firecrawl"] = post_json(
                    FIRECRAWL_URL + "/v0/search",
                    {"query": query, "limit": 5},
                )
            except Exception as exc:  # noqa: BLE001 - keep the job resilient
                out["errors"].append(
                    {"query": query, "source": "firecrawl", "error": str(exc)}
                )
        if SEARXNG_URL:
            try:
                params = urllib.parse.urlencode({"q": query, "format": "json"})
                item["searxng"] = get_json(SEARXNG_URL + "/search?" + params)
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(
                    {"query": query, "source": "searxng", "error": str(exc)}
                )
        out["results"].append(item)

    with open("data.json", "w", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"queries": len(QUERIES), "errors": len(out["errors"])}))


if __name__ == "__main__":
    main()
