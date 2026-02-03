"""Static metadata for retriever-supported tasks."""

from __future__ import annotations

from typing import Optional

RETRIEVER_TASKS: dict[str, set[str]] = {
    "tf-vector": {"index"},
    "sqlite-full-text-search": {"index"},
    "embedding-index-inmemory": {"index"},
    "embedding-index-file": {"index"},
}


def resolve_retriever_id(config: Optional[dict]) -> Optional[str]:
    """Resolve retriever identifier from a retriever config dict."""
    if not isinstance(config, dict):
        return None
    for key in ("retriever_id", "retriever_type"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def supported_retriever_tasks(retriever_id: Optional[str]) -> set[str]:
    """Return supported task names for the retriever identifier."""
    if not retriever_id:
        return set()
    return set(RETRIEVER_TASKS.get(retriever_id, set()))
