"""
Reusable printers for Context demo scripts.
"""

from __future__ import annotations

from typing import Iterable


def print_section(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{title}\n{bar}")


def shorten(text: str, max_len: int = 160) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def summarize_lines(lines: Iterable[str], limit: int = 5) -> list[str]:
    summaries = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        summaries.append(shorten(stripped, 140))
        if len(summaries) >= limit:
            break
    return summaries


def print_context_plan(title: str, items: list[str]) -> None:
    print_section(f"{title} (logical structure)")
    for item in items:
        print(f"- {item}")


def print_context_pack_snapshot(pack_name: str, blocks: list[str]) -> None:
    print_section(f"Context pack output ({pack_name})")
    for idx, block in enumerate(blocks, start=1):
        print(f"{idx}. {shorten(block, 180)}")


def print_demo_result(
    label: str, system_prompt: str, history: list[dict], user_message: str, token_count: int
) -> None:
    print(f"Context: {label}")
    print(f"Token estimate: {token_count}")
    print("System prompt:")
    print(shorten(system_prompt, 400))
    if history:
        print("History:")
        for entry in history:
            print(f"- {entry.get('role')}: {shorten(entry.get('content', ''), 120)}")
    if user_message:
        print("User message:")
        print(shorten(user_message, 200))


def print_message_tree(
    label: str,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
    context_children: list[str] | None = None,
) -> None:
    print_section(f"{label} (message list, hierarchical)")
    print("messages")
    print("└─ system")
    if context_children:
        print("   ├─ context")
        for child in context_children:
            print(f"   │  └─ system: {shorten(child, 120)}")
        print(f"   └─ system: {shorten(system_prompt, 120)}")
    else:
        print(f"   └─ system: {shorten(system_prompt, 120)}")
    if history:
        print("└─ history")
        for entry in history:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            print(f"   └─ {role}: {shorten(content, 120)}")
    if user_message:
        print(f"└─ user: {shorten(user_message, 120)}")


def print_flattened_messages(
    label: str,
    system_prompt: str,
    history: list[dict[str, str]],
    user_message: str,
) -> None:
    print_section(f"{label} (message list, flattened)")
    print("- system: " + shorten(system_prompt, 200))
    for entry in history:
        role = entry.get("role", "unknown")
        content = entry.get("content", "")
        print(f"- {role}: {shorten(content, 200)}")
    if user_message:
        print(f"- user: {shorten(user_message, 200)}")
