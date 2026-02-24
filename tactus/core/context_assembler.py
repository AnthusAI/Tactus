"""Tactus wrapper for the Biblicus Context Engine assembler."""

from __future__ import annotations

from biblicus.context_engine import ContextAssembler as BiblicusContextAssembler
from biblicus.context_engine import ContextAssemblyResult
from typing import Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class ContextAssembler(BiblicusContextAssembler):
    """
    Context assembler that defaults to Tactus test retrievers.

    :param default_retriever: Optional default retriever override.
    :type default_retriever: callable or None
    """

    def __init__(
        self,
        context_registry,
        retriever_registry: Optional[dict[str, Any]] = None,
        corpus_registry: Optional[dict[str, Any]] = None,
        compactor_registry: Optional[dict[str, Any]] = None,
        default_retriever: Optional[Any] = None,
    ):
        from tactus.core import retrieval as retrieval_module

        retriever_router = retrieval_module.make_retriever_router(
            corpus_registry, retriever_registry
        )
        super().__init__(
            context_registry,
            retriever_registry=retriever_registry,
            corpus_registry=corpus_registry,
            compactor_registry=compactor_registry,
            default_retriever=default_retriever or retriever_router,
        )

    def assemble(
        self,
        context_name: str,
        base_system_prompt: str,
        history_messages: list[dict[str, Any]],
        user_message: Optional[str],
        template_context: dict[str, Any],
        retriever_override: Optional[Any] = None,
    ):
        result = super().assemble(
            context_name=context_name,
            base_system_prompt=base_system_prompt,
            history_messages=history_messages,
            user_message=user_message,
            template_context=template_context,
            retriever_override=retriever_override,
        )
        if os.environ.get("TACTUS_TRACE_CONTEXT") == "1":
            logger.debug(
                "[CONTEXT] name=%s system_chars=%s history_items=%s user_chars=%s token_est=%s",
                context_name,
                len(result.system_prompt),
                len(result.history),
                len(result.user_message),
                result.token_count,
            )
        return result


__all__ = ["ContextAssembler", "ContextAssemblyResult"]
