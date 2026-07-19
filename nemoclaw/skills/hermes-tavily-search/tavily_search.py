#!/usr/bin/env python3
"""Run a Tavily web search through OpenShell's protected credential proxy."""

import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print(json.dumps({"error": "Provide a search query."}))
        return 2

    payload = {
        "api_key": "openshell:resolve:env:TAVILY_API_KEY",
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": True,
        "include_raw_content": False,
    }
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(response.read().decode("utf-8"))
            return 0
    except urllib.error.HTTPError as exc:
        print(json.dumps({"error": f"Tavily request failed ({exc.code})."}))
        return 1
    except urllib.error.URLError as exc:
        print(json.dumps({"error": f"Tavily connection failed: {exc.reason}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
