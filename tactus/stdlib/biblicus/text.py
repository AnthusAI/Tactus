"""
tactus.biblicus.text - Biblicus text utilities for Tactus.

This module exposes Biblicus text helpers to Lua via the stdlib loader.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


def _require_biblicus_text() -> Dict[str, Any]:
    try:
        from biblicus.ai.models import LlmClientConfig
        from biblicus.text import (
            apply_text_annotate,
            apply_text_extract,
            apply_text_link,
            apply_text_redact,
            apply_text_slice,
        )
        from biblicus.text.markup import (
            parse_span_markup,
            strip_span_tags,
            summarize_span_context,
        )
        from biblicus.text.models import (
            TextAnnotateRequest,
            TextExtractRequest,
            TextLinkRequest,
            TextRedactRequest,
            TextSliceRequest,
        )
    except ModuleNotFoundError as exc:
        raise ValueError(
            "Biblicus text utilities are unavailable. Install a Biblicus build "
            "that includes biblicus.text to use the text stdlib."
        ) from exc

    return {
        "LlmClientConfig": LlmClientConfig,
        "apply_text_annotate": apply_text_annotate,
        "apply_text_extract": apply_text_extract,
        "apply_text_link": apply_text_link,
        "apply_text_redact": apply_text_redact,
        "apply_text_slice": apply_text_slice,
        "parse_span_markup": parse_span_markup,
        "strip_span_tags": strip_span_tags,
        "summarize_span_context": summarize_span_context,
        "TextAnnotateRequest": TextAnnotateRequest,
        "TextExtractRequest": TextExtractRequest,
        "TextLinkRequest": TextLinkRequest,
        "TextRedactRequest": TextRedactRequest,
        "TextSliceRequest": TextSliceRequest,
    }


def _normalize_client_config(client: Any) -> Any:
    if not isinstance(client, dict):
        raise ValueError("client must be a table with provider and model")

    payload = dict(client)
    model = payload.get("model")
    provider = payload.get("provider")
    if not model:
        raise ValueError("client.model is required")

    if provider is None and isinstance(model, str) and "/" in model:
        provider, model = model.split("/", 1)
    elif provider is not None and isinstance(model, str) and model.startswith(f"{provider}/"):
        model = model.split("/", 1)[1]

    if provider is None:
        raise ValueError("client.provider is required when model lacks a provider prefix")

    payload["provider"] = provider
    payload["model"] = model

    biblicus = _require_biblicus_text()
    return biblicus["LlmClientConfig"](**payload)


def _prepare_request(request: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("request must be a table")

    payload = dict(request)
    mock_mode = os.environ.get("TACTUS_MOCK_MODE")
    if mock_mode == "0":
        payload.pop("mock_marked_up_text", None)
    client = payload.get("client")
    if client is None:
        raise ValueError("client is required")
    payload["client"] = _normalize_client_config(client)
    return payload


def _maybe_mock(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
    try:
        from tactus.core.mocking import get_current_mock_manager
    except Exception:
        return None
    mock_manager = get_current_mock_manager()
    if mock_manager is None:
        return None
    mock_result = mock_manager.get_mock_response(tool_name, payload)
    if mock_result is None:
        return None
    mock_manager.record_call(tool_name, payload, mock_result)
    return mock_result


def extract(request: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock("biblicus.text.extract", payload)
    if mock_result is not None:
        return mock_result
    biblicus = _require_biblicus_text()
    result = biblicus["apply_text_extract"](biblicus["TextExtractRequest"](**payload))
    return result.model_dump()


def slice(request: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock("biblicus.text.slice", payload)
    if mock_result is not None:
        return mock_result
    biblicus = _require_biblicus_text()
    result = biblicus["apply_text_slice"](biblicus["TextSliceRequest"](**payload))
    return result.model_dump()


def annotate(request: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock("biblicus.text.annotate", payload)
    if mock_result is not None:
        return mock_result
    biblicus = _require_biblicus_text()
    result = biblicus["apply_text_annotate"](biblicus["TextAnnotateRequest"](**payload))
    return result.model_dump()


def redact(request: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock("biblicus.text.redact", payload)
    if mock_result is not None:
        return mock_result
    biblicus = _require_biblicus_text()
    result = biblicus["apply_text_redact"](biblicus["TextRedactRequest"](**payload))
    return result.model_dump()


def link(request: Dict[str, Any]) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock("biblicus.text.link", payload)
    if mock_result is not None:
        return mock_result
    biblicus = _require_biblicus_text()
    result = biblicus["apply_text_link"](biblicus["TextLinkRequest"](**payload))
    return result.model_dump()


def strip_span_tags(marked_up_text: str) -> str:
    biblicus = _require_biblicus_text()
    return biblicus["strip_span_tags"](marked_up_text)


def parse_span_markup(marked_up_text: str) -> List[Dict[str, Any]]:
    biblicus = _require_biblicus_text()
    spans = biblicus["parse_span_markup"](marked_up_text)
    return [span.model_dump() for span in spans]


def summarize_span_context(marked_up_text: str, span_indices: List[int]) -> List[str]:
    biblicus = _require_biblicus_text()
    return biblicus["summarize_span_context"](marked_up_text, span_indices)


__tactus_exports__ = [
    "extract",
    "slice",
    "annotate",
    "redact",
    "link",
    "strip_span_tags",
    "parse_span_markup",
    "summarize_span_context",
]
