"""Bing Web Search provider.

Configuration::

    # ~/.hermes/.env
    BING_SEARCH_API_KEY=your-key

    # Optional endpoint override for Azure sovereign/custom deployments
    BING_SEARCH_ENDPOINT=https://api.bing.microsoft.com/v7.0/search

    # ~/.hermes/config.yaml
    web:
      search_backend: "bing"
      extract_backend: "firecrawl"

This provider implements ``WebSearchProvider`` only.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from tools.web_providers.base import WebSearchProvider

logger = logging.getLogger(__name__)

_DEFAULT_BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


class BingSearchProvider(WebSearchProvider):
    """Search via the Bing Web Search API."""

    def provider_name(self) -> str:
        return "bing"

    def is_configured(self) -> bool:
        return bool(os.getenv("BING_SEARCH_API_KEY", "").strip())

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        import httpx

        api_key = os.getenv("BING_SEARCH_API_KEY", "").strip()
        if not api_key:
            return {"success": False, "error": "BING_SEARCH_API_KEY is not set"}

        endpoint = os.getenv("BING_SEARCH_ENDPOINT", _DEFAULT_BING_ENDPOINT).strip() or _DEFAULT_BING_ENDPOINT
        count = max(1, min(int(limit), 50))

        try:
            resp = httpx.get(
                endpoint,
                params={"q": query, "count": count, "responseFilter": "Webpages"},
                headers={"Ocp-Apim-Subscription-Key": api_key, "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Bing Search HTTP error: %s", exc)
            return {"success": False, "error": f"Bing Search returned HTTP {exc.response.status_code}"}
        except httpx.RequestError as exc:
            logger.warning("Bing Search request error: %s", exc)
            return {"success": False, "error": f"Could not reach Bing Search: {exc}"}

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Bing Search response parse error: %s", exc)
            return {"success": False, "error": "Could not parse Bing Search response as JSON"}

        raw_results = (data.get("webPages") or {}).get("value", []) or []
        web_results = [
            {
                "title": str(r.get("name", "")),
                "url": str(r.get("url", "")),
                "description": str(r.get("snippet", "")),
                "position": i + 1,
            }
            for i, r in enumerate(raw_results[:limit])
        ]

        logger.info("Bing Search '%s': %d results (limit %d)", query, len(web_results), limit)
        return {"success": True, "data": {"web": web_results}}
