"""
Compare LLM output quality with a long Context pack budget.
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
from tactus.dspy.agent import create_dspy_agent
from tactus.dspy.config import configure_lm
from scripts.context_demo_config import ensure_openai_api_key_from_config
from scripts.context_demo_printer import (
    print_context_pack_snapshot,
    print_context_plan,
    print_demo_result,
    print_flattened_messages,
    print_message_tree,
    print_section,
    shorten,
)


def _build_registry(pack_max_tokens: int, query: str, wfo: str) -> RegistryBuilder:
    builder = RegistryBuilder()
    builder.register_corpus(
        "noaa_afd",
        {"wfo": wfo, "maximum_cache_total_items": 20},
    )
    builder.register_retriever(
        "noaa_search",
        {
            "corpus": "noaa_afd",
            "retriever_id": "noaa_afd",
            "query": query,
            "limit": 6,
            "maximum_total_characters": 6000,
        },
    )
    builder.register_context(
        "long_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 1800},
                "pack_budget": {"default_max_tokens": pack_max_tokens},
                "overflow": "compact",
            },
            "messages": [
                {
                    "type": "system",
                    "content": (
                        "You are a helpful assistant. Use only the provided forecast discussion "
                        "text as your source. Do not claim you lack access; the text above is authoritative."
                    ),
                },
                {"type": "context", "name": "noaa_search"},
                {"type": "history"},
                {
                    "type": "user",
                    "template": (
                        "Forecast discussion:\\n{context.noaa_search}\\n\\n"
                        "Question: {input.question}"
                    ),
                },
            ],
        },
    )
    return builder


def _print_story(
    context_name: str,
    assembled,
    pack_blocks: list[str],
    user_message: str,
) -> None:
    print_context_plan(
        "Request plan",
        [
            (
                'system("You are a helpful assistant. Use only the provided forecast discussion text as your source. '
                + 'Do not claim you lack access; the text above is authoritative.")'
            ),
            "context(noaa_search)",
            "history()",
            'user(template("Forecast discussion:\\n{context.noaa_search}\\n\\nQuestion: {input.question}"))',
        ],
    )
    print_context_pack_snapshot("noaa_search", pack_blocks)
    print_section("Rendered context")
    print_demo_result(
        context_name,
        assembled.system_prompt,
        assembled.history,
        assembled.user_message,
        assembled.token_count,
    )
    print_message_tree(
        "Rendered context",
        system_prompt=assembled.system_prompt,
        history=assembled.history,
        user_message=assembled.user_message,
        context_children=pack_blocks,
    )
    print_flattened_messages(
        "Rendered context",
        system_prompt=assembled.system_prompt,
        history=assembled.history,
        user_message=assembled.user_message,
    )


def main() -> None:
    print_section("Context Quality Demo (long pack)")
    if not ensure_openai_api_key_from_config():
        raise RuntimeError("OPENAI_API_KEY is not set and no .tactus/config.yml key was found.")
    configure_lm("openai/gpt-4o-mini", temperature=0.0)

    user_message = (
        "From the provided forecast discussion text, extract the KEY MESSAGES bullets "
        "verbatim. If the KEY MESSAGES section is missing, reply with NOT FOUND."
    )
    wfo = "MFL"
    builder = _build_registry(pack_max_tokens=800, query=user_message, wfo=wfo)

    assembler = ContextAssembler(
        builder.registry.contexts,
        retriever_registry=builder.registry.retrievers,
        corpus_registry=builder.registry.corpora,
        default_retriever=retrieve_noaa_afd,
    )
    assembled = assembler.assemble(
        context_name="long_context",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {"question": user_message}, "context": {}},
        retriever_override=None,
    )

    preview_pack = retrieve_noaa_afd(
        ContextRetrieverRequest(
            query=user_message,
            limit=4,
            maximum_total_characters=6000,
            metadata={"wfo": wfo, "maximum_cache_total_items": 20},
        ),
    )
    pack_blocks = [block.text for block in preview_pack.blocks]
    _print_story("long_context", assembled, pack_blocks, user_message)

    print_section("LLM response (long pack)")
    agent = create_dspy_agent(
        "long_pack_agent",
        {
            "model": "openai/gpt-4o-mini",
            "context": "long_context",
        },
        registry=builder.registry,
    )
    result = agent({"message": user_message})
    print(shorten(str(result.output), 1200))


if __name__ == "__main__":
    main()
