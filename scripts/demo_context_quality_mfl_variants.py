"""
Run RAG prompt variants against Miami (MFL) NOAA AFD corpus.
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


def _build_registry(
    context_name: str, messages: list[dict], query: str, wfo: str
) -> RegistryBuilder:
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
            "limit": 4,
            "maximum_total_characters": 8000,
        },
    )
    builder.register_context(
        context_name,
        {
            "policy": {
                "input_budget": {"max_tokens": 2000},
                "pack_budget": {"default_max_tokens": 1200},
                "overflow": "compact",
            },
            "messages": messages,
        },
    )
    return builder


def _run_variant(
    title: str,
    messages: list[dict],
    plan_lines: list[str],
    user_message: str,
    query: str,
    wfo: str,
) -> None:
    print_section(title)
    builder = _build_registry(title.lower().replace(" ", "_"), messages, query, wfo)

    assembler = ContextAssembler(
        builder.registry.contexts,
        retriever_registry=builder.registry.retrievers,
        corpus_registry=builder.registry.corpora,
        default_retriever=retrieve_noaa_afd,
    )

    assembled = assembler.assemble(
        context_name=title.lower().replace(" ", "_"),
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {"question": user_message}, "context": {}},
        retriever_override=None,
    )

    preview_pack = retrieve_noaa_afd(
        ContextRetrieverRequest(
            query=query,
            limit=2,
            maximum_total_characters=8000,
            metadata={"wfo": wfo, "maximum_cache_total_items": 20},
        ),
    )
    pack_blocks = [block.text for block in preview_pack.blocks]

    print_context_plan("Request plan", plan_lines)
    print_context_pack_snapshot("noaa_search", pack_blocks)
    print_section("Rendered context")
    print_demo_result(
        title.lower().replace(" ", "_"),
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

    print_section("LLM response")
    agent = create_dspy_agent(
        title.lower().replace(" ", "_") + "_agent",
        {
            "model": "openai/gpt-4o-mini",
            "context": title.lower().replace(" ", "_"),
        },
        registry=builder.registry,
    )
    result = agent({"message": user_message})
    print(shorten(str(result.output), 1600))


def main() -> None:
    if not ensure_openai_api_key_from_config():
        raise RuntimeError("OPENAI_API_KEY is not set and no .tactus/config.yml key was found.")
    configure_lm("openai/gpt-4o-mini", temperature=0.0)

    wfo = "MFL"
    user_message = (
        "From the provided forecast discussion text, extract the KEY MESSAGES bullets "
        "verbatim. If the KEY MESSAGES section is missing, reply with NOT FOUND."
    )
    query = "KEY MESSAGES Miami Area Forecast Discussion"

    _run_variant(
        "Variant 1: System context only",
        messages=[
            {
                "type": "system",
                "content": (
                    "You are a helpful assistant. Use only the provided forecast discussion "
                    "text as your source. Do not claim you lack access; the text above is authoritative."
                ),
            },
            {"type": "context", "name": "noaa_search"},
            {"type": "history"},
            {"type": "user", "template": "Question: {input.question}"},
        ],
        plan_lines=[
            'system("Use only the provided forecast discussion text as your source.")',
            "context(noaa_search)",
            "history()",
            'user(template("Question: {input.question}"))',
        ],
        user_message=user_message,
        query=query,
        wfo=wfo,
    )

    _run_variant(
        "Variant 2: User carries context",
        messages=[
            {
                "type": "system",
                "content": "You are a helpful assistant. Use only the provided forecast discussion text.",
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
        plan_lines=[
            'system("Use only the provided forecast discussion text.")',
            "context(noaa_search)",
            "history()",
            'user(template("Forecast discussion:\\n{context.noaa_search}\\n\\nQuestion: {input.question}"))',
        ],
        user_message=user_message,
        query=query,
        wfo=wfo,
    )

    _run_variant(
        "Variant 3: Strict extraction format",
        messages=[
            {
                "type": "system",
                "content": (
                    "You are a helpful assistant. Return only the KEY MESSAGES bullets from the "
                    "forecast discussion text. If not found, return NOT FOUND."
                ),
            },
            {"type": "context", "name": "noaa_search"},
            {"type": "history"},
            {
                "type": "user",
                "template": (
                    "Forecast discussion:\\n{context.noaa_search}\\n\\n"
                    "Extract KEY MESSAGES bullets verbatim."
                ),
            },
        ],
        plan_lines=[
            'system("Return only KEY MESSAGES bullets or NOT FOUND.")',
            "context(noaa_search)",
            "history()",
            'user(template("Forecast discussion:\\n{context.noaa_search}\\n\\nExtract KEY MESSAGES bullets verbatim."))',
        ],
        user_message=user_message,
        query=query,
        wfo=wfo,
    )


if __name__ == "__main__":
    main()
