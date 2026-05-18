"""Provider-backed web research primitives for the Tactus stdlib.

The Lua-facing module is `tactus.web`; this Python module is intentionally kept
behind a `.tac` facade so the public stdlib shape is documented in Tactus.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

__tactus_exports__ = [
    "providers",
    "search",
    "synthesize",
    "deep_research_start",
    "deep_research_status",
    "deep_research_result",
]


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


def providers(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return available web providers and whether their env keys are present."""

    return {
        "ok": True,
        "providers": {
            "openai": {
                "modes": ["search", "synthesis"],
                "env_key": "OPENAI_API_KEY",
                "configured": bool(os.environ.get("OPENAI_API_KEY")),
                "default_model": DEFAULT_OPENAI_MODEL,
                "supports": {
                    "allowed_domains": True,
                    "blocked_domains": True,
                    "reasoning_effort": True,
                    "return_token_budget": True,
                    "sources": True,
                },
            },
            "perplexity": {
                "modes": ["search"],
                "status": "planned",
                "configured": False,
                "supports": {
                    "domains": True,
                    "exclude_domains": True,
                    "country": True,
                    "language": True,
                    "max_results": True,
                    "max_tokens": True,
                    "max_tokens_per_page": True,
                },
            },
            "gemini": {
                "modes": ["deep_research"],
                "status": "planned",
                "configured": bool(os.environ.get("GEMINI_API_KEY")),
                "reserved_apis": [
                    "deep_research_start",
                    "deep_research_status",
                    "deep_research_result",
                ],
            },
        },
    }


def search(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a raw web search and normalize provider results."""

    args = _ensure_args(args)
    provider = str(args.get("provider") or "openai").lower()
    query = _string_arg(args, "query")

    if provider == "openai":
        return _search_openai(args, query=query)

    return _error_result(
        provider=provider,
        mode="search",
        query=query,
        code="UNSUPPORTED_PROVIDER",
        message=f"web.search does not support provider '{provider}' in this milestone.",
    )


def _search_openai(args: dict[str, Any], *, query: str) -> dict[str, Any]:
    provider = "openai"
    if not query:
        return _error_result(
            provider=provider,
            mode="search",
            query=query,
            code="MISSING_QUERY",
            message="web.search requires query.",
        )
    if args.get("mock"):
        return _mock_openai_search(provider=provider, query=query, args=args)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _error_result(
            provider=provider,
            mode="search",
            query=query,
            code="MISSING_API_KEY",
            message="OPENAI_API_KEY is required for provider 'openai'.",
        )

    payload = _build_openai_payload(args)
    try:
        raw = _post_json(
            OPENAI_RESPONSES_URL,
            payload,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:
        return _error_result(
            provider=provider,
            mode="search",
            query=query,
            code="PROVIDER_REQUEST_FAILED",
            message=str(exc),
            retryable=True,
        )

    return _normalize_openai_search_response(
        raw,
        query=query,
        request=payload,
        max_results=_positive_int(args.get("max_results") or args.get("maxResults")),
    )


def synthesize(args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Use a provider's web-capable synthesis path and normalize the answer."""

    args = _ensure_args(args)
    provider = str(args.get("provider") or "openai").lower()
    query = _string_arg(args, "query")

    if provider != "openai":
        return _error_result(
            provider=provider,
            mode="synthesis",
            query=query,
            code="UNSUPPORTED_PROVIDER",
            message=f"web.synthesize does not support provider '{provider}'.",
        )
    if not query:
        return _error_result(
            provider=provider,
            mode="synthesis",
            query=query,
            code="MISSING_QUERY",
            message="web.synthesize requires query.",
        )
    if args.get("mock"):
        return _mock_synthesis(provider=provider, query=query, args=args)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _error_result(
            provider=provider,
            mode="synthesis",
            query=query,
            code="MISSING_API_KEY",
            message="OPENAI_API_KEY is required for provider 'openai'.",
        )

    payload = _build_openai_payload(args)
    try:
        raw = _post_json(
            OPENAI_RESPONSES_URL,
            payload,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:
        return _error_result(
            provider=provider,
            mode="synthesis",
            query=query,
            code="PROVIDER_REQUEST_FAILED",
            message=str(exc),
            retryable=True,
        )

    return _normalize_openai_response(raw, query=query, request=payload)


def deep_research_start(args: dict[str, Any] | None = None) -> dict[str, Any]:
    return _deep_research_deferred("deep_research_start", args)


def deep_research_status(args: dict[str, Any] | None = None) -> dict[str, Any]:
    return _deep_research_deferred("deep_research_status", args)


def deep_research_result(args: dict[str, Any] | None = None) -> dict[str, Any]:
    return _deep_research_deferred("deep_research_result", args)


def _build_openai_payload(args: dict[str, Any]) -> dict[str, Any]:
    query = _string_arg(args, "query")
    model = str(args.get("model") or DEFAULT_OPENAI_MODEL)
    tool: dict[str, Any] = {"type": "web_search"}

    allowed_domains = _as_string_list(args.get("allowed_domains") or args.get("domains"))
    blocked_domains = _as_string_list(args.get("blocked_domains") or args.get("exclude_domains"))
    filters: dict[str, Any] = {}
    if allowed_domains:
        filters["allowed_domains"] = [_domain_without_scheme(domain) for domain in allowed_domains]
    if blocked_domains:
        filters["blocked_domains"] = [_domain_without_scheme(domain) for domain in blocked_domains]
    if filters:
        tool["filters"] = filters

    return_token_budget = _openai_return_token_budget(args.get("return_token_budget"))
    if return_token_budget is not None:
        tool["return_token_budget"] = return_token_budget

    payload: dict[str, Any] = {
        "model": model,
        "tools": [tool],
        "tool_choice": "required",
        "include": ["web_search_call.action.sources"],
        "input": query,
    }

    reasoning_effort = args.get("reasoning_effort")
    if reasoning_effort:
        payload["reasoning"] = {"effort": str(reasoning_effort)}

    return payload


def _normalize_openai_response(
    raw: dict[str, Any], *, query: str, request: dict[str, Any]
) -> dict[str, Any]:
    answer = raw.get("output_text") or _extract_output_text(raw)
    sources = _extract_sources(raw, provider="openai", query=query)

    return {
        "ok": True,
        "provider": "openai",
        "mode": "synthesis",
        "query": query,
        "answer": answer or "",
        "sources": sources,
        "metadata": {
            "id": raw.get("id"),
            "model": raw.get("model") or request.get("model"),
            "usage": raw.get("usage"),
            "source_count": len(sources),
            "request": _redact_request(request),
        },
    }


def _normalize_openai_search_response(
    raw: dict[str, Any], *, query: str, request: dict[str, Any], max_results: int | None = None
) -> dict[str, Any]:
    answer = raw.get("output_text") or _extract_output_text(raw)
    sources = _extract_sources(raw, provider="openai", query=query)
    results = []
    for source in sources[:max_results] if max_results else sources:
        results.append(
            {
                "title": source.get("title"),
                "url": source.get("url"),
                "snippet": source.get("snippet"),
                "date": source.get("date"),
                "last_updated": source.get("last_updated"),
                "rank": source.get("rank"),
                "source_domain": source.get("source_domain"),
                "evidence_candidate_id": source.get("evidence_candidate_id"),
            }
        )

    return {
        "ok": True,
        "provider": "openai",
        "mode": "search",
        "query": query,
        "results": results,
        "metadata": {
            "id": raw.get("id"),
            "model": raw.get("model") or request.get("model"),
            "usage": raw.get("usage"),
            "answer": answer or "",
            "request": _redact_request(request),
            "result_count": len(results),
            "untruncated_result_count": len(sources),
        },
    }


def _extract_output_text(raw: dict[str, Any]) -> str:
    chunks: list[str] = []
    for output in raw.get("output") or []:
        for content in output.get("content") or []:
            if isinstance(content, dict) and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks)


def _extract_sources(raw: dict[str, Any], *, provider: str, query: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []

    for item in _walk_dicts(raw):
        url = item.get("url")
        if not url:
            continue
        url = str(url)
        if url in seen:
            continue
        seen.add(url)
        rank = len(sources) + 1
        sources.append(
            {
                "title": item.get("title"),
                "url": url,
                "snippet": item.get("snippet") or item.get("text"),
                "date": item.get("date"),
                "last_updated": item.get("last_updated"),
                "rank": rank,
                "source_domain": _source_domain(url),
                "evidence_candidate_id": _evidence_candidate_id(provider, query, url),
            }
        )

    return sources


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _mock_openai_search(provider: str, query: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = _build_openai_payload(args)
    return _normalize_openai_search_response(
        {
            "id": "mock-search-response",
            "model": payload["model"],
            "output_text": f"Mock search summary for {query}.",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "title": "Mock OpenAI web source",
                                "url": "https://example.com/openai-web-source",
                                "snippet": f"Mock source for {query}",
                            }
                        ]
                    },
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 8},
        },
        query=query,
        request=payload,
    )


def _mock_synthesis(provider: str, query: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = _build_openai_payload(args)
    return _normalize_openai_response(
        {
            "id": "mock-response",
            "model": payload["model"],
            "output_text": f"Mock synthesized answer for {query}.",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "title": "Mock synthesized source",
                                "url": "https://example.com/synthesis-source",
                            }
                        ]
                    },
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 8},
        },
        query=query,
        request=payload,
    )


def _deep_research_deferred(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    args = _ensure_args(args)
    provider = str(args.get("provider") or "gemini").lower()
    return {
        "ok": False,
        "provider": provider,
        "mode": "deep_research",
        "metadata": {"api": name},
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": (
                "Gemini Deep Research is reserved for a future async stdlib milestone; "
                "this API is intentionally not implemented yet."
            ),
            "retryable": False,
        },
    }


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    return json.loads(response_body)


def _error_result(
    *,
    provider: str,
    mode: str,
    query: str,
    code: str,
    message: str,
    retryable: bool = False,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ok": False,
        "provider": provider,
        "mode": mode,
        "query": query,
        "metadata": {},
        "error": {"code": code, "message": message, "retryable": retryable},
    }
    if mode == "search":
        base["results"] = []
    if mode == "synthesis":
        base["answer"] = ""
        base["sources"] = []
    return base


def _ensure_args(args: dict[str, Any] | None) -> dict[str, Any]:
    return args or {}


def _string_arg(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if value is None:
        return ""
    return str(value)


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values = [value[key] for key in sorted(value) if isinstance(key, int)]
        if not values:
            values = list(value.values())
        return [str(item) for item in values if item]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return [str(value)]


def _openai_return_token_budget(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"default", "unlimited"}:
        return normalized
    raise ValueError("OpenAI web_search return_token_budget must be 'default' or 'unlimited'.")


def _positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _domain_without_scheme(domain: str) -> str:
    parsed = urllib.parse.urlparse(domain)
    if parsed.netloc:
        return parsed.netloc
    return domain.split("/", 1)[0]


def _source_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc


def _evidence_candidate_id(provider: str, query: str, url: str) -> str:
    digest = hashlib.sha256(f"{provider}|{query}|{url}".encode("utf-8")).hexdigest()[:20]
    return f"evidence-candidate-{digest}"


def _redact_request(request: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(request))
