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
    if not model:
        raise ValueError("client.model is required")

    provider, model = _resolve_provider_and_model(payload.get("provider"), model)
    payload["provider"] = provider
    payload["model"] = model

    biblicus = _require_biblicus_text()
    return biblicus["LlmClientConfig"](**payload)


def _resolve_provider_and_model(provider: str | None, model: Any) -> tuple[str, Any]:
    if provider is None and isinstance(model, str) and "/" in model:
        provider, model = model.split("/", 1)
    elif provider is not None and isinstance(model, str) and model.startswith(f"{provider}/"):
        model = model.split("/", 1)[1]

    if provider is None:
        raise ValueError("client.provider is required when model lacks a provider prefix")

    return provider, model


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
    mock_manager = _get_mock_manager()
    if mock_manager is None:
        return None
    mock_result = mock_manager.get_mock_response(tool_name, payload)
    if mock_result is None:
        return None
    mock_manager.record_call(tool_name, payload, mock_result)
    return mock_result


def _get_mock_manager() -> Any | None:
    try:
        from tactus.core.mocking import get_current_mock_manager
    except Exception:
        return None
    return get_current_mock_manager()


def _run_text_tool(
    request: Dict[str, Any],
    *,
    tool_name: str,
    request_model_key: str,
    apply_key: str,
) -> Dict[str, Any]:
    payload = _prepare_request(request)
    mock_result = _maybe_mock(tool_name, payload)
    if mock_result is not None:
        return mock_result
    mock_marked_up_text = payload.pop("mock_marked_up_text", None)
    if mock_marked_up_text is not None:
        return _build_mock_result(tool_name, mock_marked_up_text)
    biblicus = _require_biblicus_text()
    result = biblicus[apply_key](biblicus[request_model_key](**payload))
    return result.model_dump()


def _build_mock_result(tool_name: str, mock_marked_up_text: str) -> Dict[str, Any]:
    """Build deterministic mock results from mock markup."""
    biblicus = _require_biblicus_text()
    if tool_name == "biblicus.text.slice":
        slices = _build_slices_from_markup(mock_marked_up_text)
        return {
            "marked_up_text": mock_marked_up_text,
            "slices": slices,
            "warnings": [],
        }
    spans = biblicus["parse_span_markup"](mock_marked_up_text)
    return {
        "marked_up_text": mock_marked_up_text,
        "spans": [span.model_dump() for span in spans],
        "warnings": [],
    }


def _build_slices_from_markup(marked_up_text: str) -> List[Dict[str, Any]]:
    """Build slice metadata based on mock <slice/> markers."""
    parts = marked_up_text.split("<slice/>")
    slices: List[Dict[str, Any]] = []
    cursor = 0
    for index, text in enumerate(parts, start=1):
        start_char = cursor
        end_char = start_char + len(text)
        slices.append(
            {
                "index": index,
                "start_char": start_char,
                "end_char": end_char,
                "text": text,
            }
        )
        cursor = end_char
    return slices


def extract(request: Dict[str, Any]) -> Dict[str, Any]:
    return _run_text_tool(
        request,
        tool_name="biblicus.text.extract",
        request_model_key="TextExtractRequest",
        apply_key="apply_text_extract",
    )


def slice(request: Dict[str, Any]) -> Dict[str, Any]:
    return _run_text_tool(
        request,
        tool_name="biblicus.text.slice",
        request_model_key="TextSliceRequest",
        apply_key="apply_text_slice",
    )


def annotate(request: Dict[str, Any]) -> Dict[str, Any]:
    return _run_text_tool(
        request,
        tool_name="biblicus.text.annotate",
        request_model_key="TextAnnotateRequest",
        apply_key="apply_text_annotate",
    )


def redact(request: Dict[str, Any]) -> Dict[str, Any]:
    return _run_text_tool(
        request,
        tool_name="biblicus.text.redact",
        request_model_key="TextRedactRequest",
        apply_key="apply_text_redact",
    )


def link(request: Dict[str, Any]) -> Dict[str, Any]:
    return _run_text_tool(
        request,
        tool_name="biblicus.text.link",
        request_model_key="TextLinkRequest",
        apply_key="apply_text_link",
    )


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
