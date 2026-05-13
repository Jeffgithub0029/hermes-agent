"""SerpAPI web search provider.

Configuration::

    # ~/.hermes/.env
    SERPAPI_API_KEY=your-key

    # Optional endpoint override
    SERPAPI_ENDPOINT=https://serpapi.com/search.json

    # ~/.hermes/config.yaml
    web:
      search_backend: "serpapi"
      extract_backend: "firecrawl"

This provider implements ``WebSearchProvider`` only.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from tools.web_providers.base import WebSearchProvider

logger = logging.getLogger(__name__)

_DEFAULT_SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class SerpApiSearchProvider(WebSearchProvider):
    """Search via SerpAPI."""

    def provider_name(self) -> str:
        return "serpapi"

    def is_configured(self) -> bool:
        return bool(os.getenv("SERPAPI_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        import httpx

        api_key = os.getenv("SERPAPI_API_KEY", "").strip()
        if not api_key:
            return {"success": False, "error": "SERPAPI_API_KEY is not set"}

        endpoint = os.getenv("SERPAPI_ENDPOINT", _DEFAULT_SERPAPI_ENDPOINT).strip() or _DEFAULT_SERPAPI_ENDPOINT
        count = max(1, min(int(limit), 100))

        try:
            resp = httpx.get(
                endpoint,
                params={"q": query, "engine": "google", "num": count, "api_key": api_key},
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("SerpAPI HTTP error: %s", exc)
            return {"success": False, "error": f"SerpAPI returned HTTP {exc.response.status_code}"}
        except httpx.RequestError as exc:
            logger.warning("SerpAPI request error: %s", exc)
            return {"success": False, "error": f"Could not reach SerpAPI: {exc}"}

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SerpAPI response parse error: %s", exc)
            return {"success": False, "error": "Could not parse SerpAPI response as JSON"}

        raw_results = data.get("organic_results", []) or []
        web_results = [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("link", "")),
                "description": str(r.get("snippet", "")),
                "position": i + 1,
            }
            for i, r in enumerate(raw_results[:limit])
        ]

        logger.info("SerpAPI search '%s': %d results (limit %d)", query, len(web_results), limit)
        return {"success": True, "data": {"web": web_results}}
