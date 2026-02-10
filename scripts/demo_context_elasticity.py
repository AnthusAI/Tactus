"""
Compare Context pack outputs using two different token budgets.
"""

from __future__ import annotations

# ruff: noqa: E402

from pathlib import Path
import sys


def _ensure_repo_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()

from biblicus.context_engine import ContextRetrieverRequest
from tactus.core.context_assembler import ContextAssembler
from tactus.core.registry import RegistryBuilder
from tactus.core.retrieval import retrieve_noaa_afd
from scripts.context_demo_printer import print_demo_result, print_message_tree, print_section


def main() -> None:
    print_section("Context Elasticity Demo")

    user_message = (
        "Based only on the provided forecast discussion text, summarize what the weather "
        "has been like lately in Miami."
    )
    query = user_message
    wfo = "MFL"

    short_pack_tokens = 200
    long_pack_tokens = 1200

    short_builder = RegistryBuilder()
    short_builder.register_corpus(
        "noaa_afd",
        {"wfo": wfo, "maximum_cache_total_items": 20},
    )
    short_builder.register_retriever(
        "noaa_search",
        {
            "corpus": "noaa_afd",
            "retriever_id": "noaa_afd",
            "query": query,
            "limit": 4,
            "maximum_total_characters": 20000,
        },
    )
    short_builder.register_context(
        "short_pack",
        {
            "policy": {
                "input_budget": {"max_tokens": 1600},
                "pack_budget": {"default_max_tokens": short_pack_tokens},
                "overflow": "compact",
            },
            "messages": [
                {
                    "type": "system",
                    "content": "Use only the provided forecast discussion text as your source.",
                },
                {"type": "context", "name": "noaa_search"},
                {"type": "history"},
                {"type": "user", "template": "Question: {input.question}"},
            ],
        },
    )

    long_builder = RegistryBuilder()
    long_builder.register_corpus(
        "noaa_afd",
        {"wfo": wfo, "maximum_cache_total_items": 20},
    )
    long_builder.register_retriever(
        "noaa_search",
        {
            "corpus": "noaa_afd",
            "retriever_id": "noaa_afd",
            "query": query,
            "limit": 4,
            "maximum_total_characters": 20000,
        },
    )
    long_builder.register_context(
        "long_pack",
        {
            "policy": {
                "input_budget": {"max_tokens": 3600},
                "pack_budget": {"default_max_tokens": long_pack_tokens},
                "overflow": "compact",
            },
            "messages": [
                {
                    "type": "system",
                    "content": "Use only the provided forecast discussion text as your source.",
                },
                {"type": "context", "name": "noaa_search"},
                {"type": "history"},
                {"type": "user", "template": "Question: {input.question}"},
            ],
        },
    )

    short_assembler = ContextAssembler(
        short_builder.registry.contexts,
        retriever_registry=short_builder.registry.retrievers,
        corpus_registry=short_builder.registry.corpora,
        default_retriever=retrieve_noaa_afd,
    )
    long_assembler = ContextAssembler(
        long_builder.registry.contexts,
        retriever_registry=long_builder.registry.retrievers,
        corpus_registry=long_builder.registry.corpora,
        default_retriever=retrieve_noaa_afd,
    )

    template_context = {"input": {"question": user_message}, "context": {}}

    short_context = short_assembler.assemble(
        context_name="short_pack",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context=template_context,
        retriever_override=None,
    )
    long_context = long_assembler.assemble(
        context_name="long_pack",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context=template_context,
        retriever_override=None,
    )

    short_pack_request = ContextRetrieverRequest(
        query=query,
        limit=4,
        maximum_total_characters=int(short_pack_tokens) * 4,
        max_tokens=short_pack_tokens,
        metadata={
            "wfo": wfo,
            "maximum_cache_total_items": 20,
        },
    )
    long_pack_request = ContextRetrieverRequest(
        query=query,
        limit=4,
        maximum_total_characters=int(long_pack_tokens) * 4,
        max_tokens=long_pack_tokens,
        metadata={
            "wfo": wfo,
            "maximum_cache_total_items": 20,
        },
    )

    short_pack = retrieve_noaa_afd(short_pack_request)
    long_pack = retrieve_noaa_afd(long_pack_request)

    print_section("Short pack")
    print("Context name: short_pack")
    print(f"Pack tokens (budgeted): {short_pack_tokens}")
    short_context_spec = short_assembler._context_registry["short_pack"]
    short_pack_text = short_assembler._render_pack(
        "noaa_search",
        template_context,
        retriever_override=None,
        pack_budget=None,
        policy=short_context_spec.policy,
    )
    print(f"Pack characters: {len(short_pack_text)}")
    print(f"Evidence blocks: {short_pack.evidence_count}")
    print("Pack text:")
    print(short_pack.text)

    print_section("Short assembled context")
    print_demo_result(
        "short_pack",
        short_context.system_prompt,
        short_context.history,
        short_context.user_message,
        short_context.token_count,
    )
    print_message_tree(
        "Short assembled context",
        system_prompt=short_context.system_prompt,
        history=short_context.history,
        user_message=short_context.user_message,
    )

    print_section("Long pack")
    print("Context name: long_pack")
    print(f"Pack tokens (budgeted): {long_pack_tokens}")
    long_context_spec = long_assembler._context_registry["long_pack"]
    long_pack_text = long_assembler._render_pack(
        "noaa_search",
        template_context,
        retriever_override=None,
        pack_budget=None,
        policy=long_context_spec.policy,
    )
    print(f"Pack characters: {len(long_pack_text)}")
    print(f"Evidence blocks: {long_pack.evidence_count}")
    print("Pack text:")
    print(long_pack.text)

    print_section("Long assembled context")
    print_demo_result(
        "long_pack",
        long_context.system_prompt,
        long_context.history,
        long_context.user_message,
        long_context.token_count,
    )
    print_message_tree(
        "Long assembled context",
        system_prompt=long_context.system_prompt,
        history=long_context.history,
        user_message=long_context.user_message,
    )


if __name__ == "__main__":
    main()
