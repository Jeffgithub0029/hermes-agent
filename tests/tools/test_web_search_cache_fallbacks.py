from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_web_search_cache_hit_skips_provider(tmp_path, monkeypatch):
    from tools import web_tools

    monkeypatch.setenv("WEB_SEARCH_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "tavily", "search_cache": {"enabled": True, "ttl_seconds": 3600}})
    monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "tavily")
    monkeypatch.setattr(web_tools, "_configured_search_fallbacks", lambda primary: [])
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

    cached = {"success": True, "data": {"web": [{"title": "Cached", "url": "https://cached.example", "description": "hit", "position": 1}]}}
    web_tools._write_web_search_cache("tavily", "same query", 5, cached)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("provider should not be called on cache hit")

    monkeypatch.setattr(web_tools, "_execute_search_backend", fail_if_called)
    result = json.loads(web_tools.web_search_tool("same query", 5))

    assert result["success"] is True
    assert result["cached"] is True
    assert result["data"]["web"][0]["title"] == "Cached"


def test_web_search_falls_back_from_tavily_to_bing(tmp_path, monkeypatch):
    from tools import web_tools

    monkeypatch.setenv("WEB_SEARCH_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(web_tools, "_load_web_config", lambda: {"backend": "tavily", "search_cache": {"enabled": False}, "search_fallbacks": ["bing"]})
    monkeypatch.setattr(web_tools, "_get_search_backend", lambda: "tavily")
    monkeypatch.setattr(web_tools, "_is_backend_available", lambda backend: backend == "bing")
    monkeypatch.setattr("tools.interrupt.is_interrupted", lambda: False, raising=False)

    calls = []

    def fake_execute(backend, query, limit):
        calls.append(backend)
        if backend == "tavily":
            raise RuntimeError("quota exhausted")
        return {"success": True, "data": {"web": [{"title": "Bing", "url": "https://bing.example", "description": "fallback", "position": 1}]}}

    monkeypatch.setattr(web_tools, "_execute_search_backend", fake_execute)
    result = json.loads(web_tools.web_search_tool("fallback query", 5))

    assert calls == ["tavily", "bing"]
    assert result["success"] is True
    assert result["backend"] == "bing"
    assert result["fallback_from"] == "tavily"
    assert result["data"]["web"][0]["title"] == "Bing"


class TestBingProvider:
    @staticmethod
    def _mock_resp(json_data, status_code=200):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = json_data
        m.raise_for_status = MagicMock()
        return m

    def test_bing_normalizes_results_and_headers(self, monkeypatch):
        monkeypatch.setenv("BING_SEARCH_API_KEY", "bing-key")
        from tools.web_providers.bing import BingSearchProvider

        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["params"] = kwargs.get("params", {})
            return self._mock_resp({"webPages": {"value": [{"name": "A", "url": "https://a.example", "snippet": "desc"}]}})

        with patch("httpx.get", side_effect=fake_get):
            result = BingSearchProvider().search("q", 5)

        assert result["success"] is True
        assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "bing-key"
        assert captured["params"]["q"] == "q"
        assert result["data"]["web"][0] == {"title": "A", "url": "https://a.example", "description": "desc", "position": 1}


class TestSerpApiProvider:
    @staticmethod
    def _mock_resp(json_data, status_code=200):
        m = MagicMock()
        m.status_code = status_code
        m.json.return_value = json_data
        m.raise_for_status = MagicMock()
        return m

    def test_serpapi_normalizes_results_and_params(self, monkeypatch):
        monkeypatch.setenv("SERPAPI_API_KEY", "serp-key")
        from tools.web_providers.serpapi import SerpApiSearchProvider

        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params", {})
            return self._mock_resp({"organic_results": [{"title": "A", "link": "https://a.example", "snippet": "desc"}]})

        with patch("httpx.get", side_effect=fake_get):
            result = SerpApiSearchProvider().search("q", 5)

        assert result["success"] is True
        assert captured["params"]["api_key"] == "serp-key"
        assert captured["params"]["engine"] == "google"
        assert result["data"]["web"][0] == {"title": "A", "url": "https://a.example", "description": "desc", "position": 1}
