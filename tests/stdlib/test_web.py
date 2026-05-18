from tactus.core.lua_sandbox import LuaSandbox
from tactus.stdlib.web import impl


def test_openai_payload_maps_web_search_filters_reasoning_and_token_budget():
    payload = impl._build_openai_payload(
        {
            "query": "automated publication systems",
            "model": "gpt-5.4-mini",
            "allowed_domains": ["https://openai.com/docs"],
            "blocked_domains": ["reddit.com"],
            "reasoning_effort": "low",
            "return_token_budget": "unlimited",
        }
    )

    assert payload["model"] == "gpt-5.4-mini"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["include"] == ["web_search_call.action.sources"]
    assert payload["tools"] == [
        {
            "type": "web_search",
            "filters": {
                "allowed_domains": ["openai.com"],
                "blocked_domains": ["reddit.com"],
            },
            "return_token_budget": "unlimited",
        }
    ]


def test_openai_payload_accepts_generic_search_domain_aliases():
    payload = impl._build_openai_payload(
        {
            "query": "automated publication systems",
            "domains": ["example.com"],
            "exclude_domains": ["reddit.com"],
            "return_token_budget": "default",
        }
    )

    assert payload["tools"][0]["filters"] == {
        "allowed_domains": ["example.com"],
        "blocked_domains": ["reddit.com"],
    }
    assert payload["tools"][0]["return_token_budget"] == "default"


def test_openai_payload_rejects_integer_return_token_budget():
    try:
        impl._build_openai_payload(
            {
                "query": "automated publication systems",
                "return_token_budget": 1200,
            }
        )
    except ValueError as exc:
        assert "return_token_budget" in str(exc)
    else:
        raise AssertionError("Expected invalid integer token budget to fail")


def test_openai_normalization_extracts_sources_recursively():
    result = impl._normalize_openai_response(
        {
            "id": "resp-id",
            "model": "gpt-5.4-mini",
            "output_text": "Answer",
            "output": [
                {
                    "action": {
                        "sources": [
                            {"title": "Source", "url": "https://example.com/source"},
                            {"title": "Duplicate", "url": "https://example.com/source"},
                        ]
                    }
                }
            ],
            "usage": {"input_tokens": 12},
        },
        query="query",
        request={"model": "gpt-5.4-mini"},
    )

    assert result["ok"] is True
    assert result["answer"] == "Answer"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["source_domain"] == "example.com"
    assert result["metadata"]["source_count"] == 1


def test_openai_search_normalization_returns_results_from_sources():
    result = impl._normalize_openai_search_response(
        {
            "id": "resp-id",
            "model": "gpt-5.4-mini",
            "output_text": "Answer",
            "output": [
                {
                    "action": {
                        "sources": [
                            {
                                "title": "Source",
                                "url": "https://example.com/source",
                                "snippet": "Snippet",
                            }
                        ]
                    }
                }
            ],
            "usage": {"input_tokens": 12},
        },
        query="query",
        request={"model": "gpt-5.4-mini"},
    )

    assert result["ok"] is True
    assert result["provider"] == "openai"
    assert result["mode"] == "search"
    assert result["results"][0]["source_domain"] == "example.com"
    assert result["metadata"]["answer"] == "Answer"


def test_search_missing_openai_key_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = impl.search({"provider": "openai", "query": "newsroom"})

    assert result["ok"] is False
    assert result["error"]["code"] == "MISSING_API_KEY"
    assert result["results"] == []


def test_perplexity_search_is_reserved_not_active():
    result = impl.search({"provider": "perplexity", "query": "newsroom", "mock": True})

    assert result["ok"] is False
    assert result["error"]["code"] == "UNSUPPORTED_PROVIDER"


def test_synthesize_missing_openai_key_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = impl.synthesize({"provider": "openai", "query": "newsroom"})

    assert result["ok"] is False
    assert result["error"]["code"] == "MISSING_API_KEY"
    assert result["sources"] == []


def test_search_uses_openai_without_provider_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def fake_post(url, payload, headers):
        calls.append((url, payload, headers))
        return {"output_text": "Answer", "output": []}

    monkeypatch.setattr(impl, "_post_json", fake_post)

    result = impl.search(
        {
            "provider": "openai",
            "query": "newsroom",
            "allowed_domains": ["example.com"],
            "return_token_budget": "unlimited",
            "max_results": 1,
        }
    )

    assert result["ok"] is True
    assert calls[0][0] == impl.OPENAI_RESPONSES_URL
    assert calls[0][1]["tool_choice"] == "required"
    assert calls[0][1]["tools"][0]["filters"]["allowed_domains"] == ["example.com"]
    assert calls[0][1]["tools"][0]["return_token_budget"] == "unlimited"
    assert calls[0][2]["Authorization"] == "Bearer test-key"


def test_synthesize_uses_openai_without_provider_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def fake_post(url, payload, headers):
        calls.append((url, payload, headers))
        return {"output_text": "Answer", "output": []}

    monkeypatch.setattr(impl, "_post_json", fake_post)

    result = impl.synthesize(
        {
            "provider": "openai",
            "query": "newsroom",
            "model": "gpt-5.4-mini",
            "allowed_domains": ["example.com"],
        }
    )

    assert result["ok"] is True
    assert calls[0][0] == impl.OPENAI_RESPONSES_URL
    assert calls[0][1]["tools"][0]["filters"]["allowed_domains"] == ["example.com"]
    assert calls[0][2]["Authorization"] == "Bearer test-key"


def test_require_tactus_web_from_lua(tmp_path):
    sandbox = LuaSandbox(base_path=str(tmp_path))

    result = sandbox.execute("""
        local web = require("tactus.web")
        local providers = web.providers{}
        local search = web.search{
            provider = "openai",
            query = "automated publication systems",
            mock = true
        }
        local synthesis = web.synthesize{
            provider = "openai",
            query = "automated publication systems",
            mock = true
        }
        return {
            has_providers = providers.providers.perplexity ~= nil and providers.providers.openai ~= nil,
            search_ok = search.ok,
            synthesis_ok = synthesis.ok,
            first_domain = search.results[1].source_domain,
            source_domain = synthesis.sources[1].source_domain
        }
        """)

    assert result["has_providers"] is True
    assert result["search_ok"] is True
    assert result["synthesis_ok"] is True
    assert result["first_domain"] == "example.com"
    assert result["source_domain"] == "example.com"


def test_deep_research_reserved_api_is_not_implemented():
    result = impl.deep_research_start({"provider": "gemini", "query": "newsroom"})

    assert result["ok"] is False
    assert result["provider"] == "gemini"
    assert result["error"]["code"] == "NOT_IMPLEMENTED"
