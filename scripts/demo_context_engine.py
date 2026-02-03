"""
Demonstrate the Context engine behavior with real Wikitext2 retrieval.
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
from tactus.core.retrieval import ensure_wikitext2_raw, load_wikitext2_texts, retrieve_wikitext2
from scripts.context_demo_printer import (
    print_context_pack_snapshot,
    print_context_plan,
    print_demo_result,
    print_flattened_messages,
    print_message_tree,
    print_section,
    shorten,
    summarize_lines,
)


def _assemble_context(
    builder: RegistryBuilder,
    context_name: str,
    base_system_prompt: str,
    history_messages: list[dict[str, str]],
    user_message: str,
    template_context: dict,
    retriever_override=None,
) -> object:
    assembler = ContextAssembler(
        builder.registry.contexts,
        retriever_registry=builder.registry.retrievers,
        corpus_registry=builder.registry.corpora,
        default_retriever=retrieve_wikitext2,
    )
    assembled = assembler.assemble(
        context_name=context_name,
        base_system_prompt=base_system_prompt,
        history_messages=history_messages,
        user_message=user_message,
        template_context=template_context,
        retriever_override=retriever_override,
    )
    return assembled


def main() -> None:
    print_section("Context Engine Demo (Tactus)")
    cache_dir = ensure_wikitext2_raw()
    print(f"Wikitext2 cache: {cache_dir}")

    print_section("Corpus snapshot")
    sample_lines = load_wikitext2_texts("train", limit=200)
    summaries = summarize_lines(sample_lines, limit=5)
    for idx, summary in enumerate(summaries, start=1):
        print(f"{idx}. {summary}")

    print_section("Direct retrieval")
    request = ContextRetrieverRequest(
        query="Valkyria Chronicles III",
        limit=3,
        maximum_total_characters=600,
        metadata={"split": "train", "maximum_cache_total_items": 2000},
    )
    pack = retrieve_wikitext2(request)
    print(f"Evidence count: {pack.evidence_count}")
    for block in pack.blocks:
        print(f"- {block.evidence_item_id}: {shorten(block.text, 160)}")

    print_section("Dual concept retrieval (full corpus)")
    concept_queries = [
        ("Valkyria Chronicles III", "gaming"),
        ("United States", "geopolitics"),
    ]
    for query_text, label in concept_queries:
        concept_request = ContextRetrieverRequest(
            query=query_text,
            limit=2,
            maximum_total_characters=400,
            metadata={"split": "train"},
        )
        concept_pack = retrieve_wikitext2(concept_request)
        print(f"Query ({label}): {query_text}")
        for block in concept_pack.blocks:
            print(f"- {block.evidence_item_id}: {shorten(block.text, 140)}")

    builder = RegistryBuilder()
    builder.register_corpus(
        "wikitext",
        {"split": "train", "maximum_cache_total_items": 2000},
    )
    builder.register_retriever(
        "wikitext_search",
        {
            "corpus": "wikitext",
            "retriever_id": "wikitext2",
            "query": "Valkyria Chronicles III",
            "limit": 3,
            "maximum_total_characters": 600,
        },
    )

    builder.register_context(
        "default_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 120},
                "pack_budget": {"default_ratio": 0.6},
                "overflow": "compact",
            },
            "packs": [{"name": "wikitext_search"}],
        },
    )

    builder.register_context(
        "explicit_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 120},
                "pack_budget": {"default_ratio": 0.6},
                "overflow": "compact",
            },
            "messages": [
                {"type": "system", "content": "You are a researcher."},
                {"type": "context", "name": "wikitext_search"},
                {"type": "history"},
                {"type": "user", "content": "Summarize the evidence."},
            ],
        },
    )

    print_context_plan(
        "Default context",
        [
            'system("You are a support agent.")',
            "context(wikitext_search)",
            "history()",
            'user("<none>")',
        ],
    )
    default_pack = retrieve_wikitext2(
        ContextRetrieverRequest(
            query="Valkyria Chronicles III",
            limit=2,
            maximum_total_characters=400,
            metadata={"split": "train", "maximum_cache_total_items": 2000},
        ),
    )
    print_context_pack_snapshot(
        "wikitext_search",
        [block.text for block in default_pack.blocks],
    )
    print_section("Default context assembly (rendered)")
    default_result = _assemble_context(
        builder,
        "default_context",
        base_system_prompt="You are a support agent.",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
    )
    print_demo_result(
        "default_context",
        default_result.system_prompt,
        default_result.history,
        default_result.user_message,
        default_result.token_count,
    )
    print_message_tree(
        "Default context",
        system_prompt=default_result.system_prompt,
        history=default_result.history,
        user_message=default_result.user_message,
        context_children=[block.text for block in default_pack.blocks],
    )
    print_flattened_messages(
        "Default context",
        system_prompt=default_result.system_prompt,
        history=default_result.history,
        user_message=default_result.user_message,
    )

    print_context_plan(
        "Explicit context with history",
        [
            'system("You are a researcher.")',
            "context(wikitext_search)",
            "history()",
            'user("Summarize the evidence.")',
        ],
    )
    print_context_pack_snapshot(
        "wikitext_search",
        [block.text for block in default_pack.blocks],
    )
    print_section("Explicit context assembly (rendered)")
    history = [
        {"role": "user", "content": "What is Valkyria Chronicles?"},
        {"role": "assistant", "content": "It is a tactical RPG series."},
    ]
    explicit_result = _assemble_context(
        builder,
        "explicit_context",
        base_system_prompt="",
        history_messages=history,
        user_message="",
        template_context={"input": {}, "context": {}},
    )
    print_demo_result(
        "explicit_context",
        explicit_result.system_prompt,
        explicit_result.history,
        explicit_result.user_message,
        explicit_result.token_count,
    )
    print_message_tree(
        "Explicit context with history",
        system_prompt=explicit_result.system_prompt,
        history=explicit_result.history,
        user_message=explicit_result.user_message,
        context_children=[block.text for block in default_pack.blocks],
    )
    print_flattened_messages(
        "Explicit context with history",
        system_prompt=explicit_result.system_prompt,
        history=explicit_result.history,
        user_message=explicit_result.user_message,
    )

    print_context_plan(
        "Expansion and pagination",
        [
            'system("Evidence:")',
            "context(paged_retriever)",
            'user("Give highlights.")',
        ],
    )
    builder.register_retriever(
        "paged_retriever",
        {
            "corpus": "wikitext",
            "query": "the",
            "limit": 1,
            "maximum_total_characters": 600,
        },
    )
    builder.register_context(
        "expanding_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 400},
                "pack_budget": {"default_ratio": 1.0},
                "overflow": "compact",
                "expansion": {"max_pages": 3, "min_fill_ratio": 0.9},
            },
            "messages": [
                {"type": "system", "content": "Evidence:"},
                {"type": "context", "name": "paged_retriever"},
                {"type": "user", "content": "Give highlights."},
            ],
        },
    )

    expansion_calls: list[int] = []
    expansion_snippets: list[tuple[int, str]] = []

    def logging_retriever(request: ContextRetrieverRequest):
        expansion_calls.append(request.offset)
        pack = retrieve_wikitext2(request)
        if pack.blocks:
            expansion_snippets.append((request.offset, pack.blocks[0].text))
        return pack

    expanding_result = _assemble_context(
        builder,
        "expanding_context",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=logging_retriever,
    )
    print_section("Pagination requests")
    print(f"Offsets requested: {expansion_calls}")
    print("Each offset is a paginated request for more evidence.")
    print_section("Context pack pages (paged_retriever)")
    for offset, snippet in expansion_snippets:
        print(f"- offset {offset}: {shorten(snippet, 160)}")
    print_section("Expansion context assembly (rendered)")
    print_demo_result(
        "expanding_context",
        expanding_result.system_prompt,
        expanding_result.history,
        expanding_result.user_message,
        expanding_result.token_count,
    )
    print_message_tree(
        "Expansion context",
        system_prompt=expanding_result.system_prompt,
        history=expanding_result.history,
        user_message=expanding_result.user_message,
        context_children=[snippet for _, snippet in expansion_snippets],
    )
    print_flattened_messages(
        "Expansion context",
        system_prompt=expanding_result.system_prompt,
        history=expanding_result.history,
        user_message=expanding_result.user_message,
    )

    print_context_plan(
        "Regeneration and compaction",
        [
            'system("Evidence: Please summarize the evidence with precision.")',
            "context(wikitext_search)",
            'user("Summarize quickly and focus on the key facts.")',
        ],
    )
    builder.register_context(
        "compact_context",
        {
            "policy": {
                "input_budget": {"max_tokens": 20},
                "pack_budget": {"default_ratio": 1.0},
                "overflow": "compact",
                "max_iterations": 3,
            },
            "messages": [
                {
                    "type": "system",
                    "content": "Evidence: Please summarize the evidence with precision.",
                },
                {"type": "context", "name": "wikitext_search"},
                {"type": "user", "content": "Summarize quickly and focus on the key facts."},
            ],
        },
    )

    compaction_calls: list[int | None] = []
    compaction_snippets: list[tuple[int | None, str]] = []

    def compacting_retriever(request: ContextRetrieverRequest):
        compaction_calls.append(request.maximum_total_characters)
        pack = retrieve_wikitext2(request)
        if pack.blocks:
            compaction_snippets.append((request.maximum_total_characters, pack.blocks[0].text))
        return pack

    compact_result = _assemble_context(
        builder,
        "compact_context",
        base_system_prompt="",
        history_messages=[],
        user_message="",
        template_context={"input": {}, "context": {}},
        retriever_override=compacting_retriever,
    )
    print_section("Compaction attempts")
    print(f"Pack budgets: {compaction_calls}")
    print("Each budget is the maximum characters allowed for the pack on that attempt.")
    print_section("Compaction pack snapshots (wikitext_search)")
    for budget, snippet in compaction_snippets:
        print(f"- budget {budget}: {shorten(snippet, 140)}")
    print_section("Compaction context assembly (rendered)")
    print_demo_result(
        "compact_context",
        compact_result.system_prompt,
        compact_result.history,
        compact_result.user_message,
        compact_result.token_count,
    )
    print_message_tree(
        "Compaction context",
        system_prompt=compact_result.system_prompt,
        history=compact_result.history,
        user_message=compact_result.user_message,
        context_children=[snippet for _, snippet in compaction_snippets],
    )
    print_flattened_messages(
        "Compaction context",
        system_prompt=compact_result.system_prompt,
        history=compact_result.history,
        user_message=compact_result.user_message,
    )


if __name__ == "__main__":
    main()
