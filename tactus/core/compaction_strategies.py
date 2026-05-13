"""
Compaction strategies for managing message history when it exceeds token budgets.

Provides pluggable strategies for compressing conversation history while
preserving recent context and key information.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SUMMARY_PROMPT = """Summarize the following conversation turns in 3-5 bullet points.
Focus on:
- Key decisions made
- Facts established
- Tasks in progress or completed
- Context needed for continuity

Be concise but preserve important identifiers, names, and references."""


class CompactionStrategy(ABC):
    """Abstract base class for message history compaction strategies."""

    @abstractmethod
    def should_compact(
        self,
        messages: List[Dict[str, Any]],
        estimated_tokens: int,
        max_tokens: int,
    ) -> bool:
        """Determine if compaction should be triggered.

        Args:
            messages: Current message history
            estimated_tokens: Estimated token count for messages
            max_tokens: Maximum allowed tokens

        Returns:
            True if compaction should be performed
        """
        pass

    @abstractmethod
    def compact(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Compact message history to fit within budget.

        Args:
            messages: Messages to compact
            max_tokens: Target token budget

        Returns:
            Tuple of (compacted_messages, compaction_metadata)
            Metadata includes:
                - summary: str (generated summary text)
                - tokens_before: int
                - tokens_after: int
                - messages_summarized: int
                - messages_retained: int
        """
        pass


class RollingSummaryStrategy(CompactionStrategy):
    """Compaction strategy that generates LLM summaries of old turns."""

    def __init__(
        self,
        llm_backend,
        recent_window: int = 10,
        summary_prompt_template: str = DEFAULT_SUMMARY_PROMPT,
    ):
        """Initialize rolling summary strategy.

        Args:
            llm_backend: LLM instance for generating summaries (must have .invoke() method)
            recent_window: Number of recent messages to preserve uncompressed
            summary_prompt_template: Template for summary generation prompt
        """
        self.llm = llm_backend
        self.recent_window = recent_window
        self.summary_prompt_template = summary_prompt_template

    def should_compact(
        self,
        messages: List[Dict[str, Any]],
        estimated_tokens: int,
        max_tokens: int,
    ) -> bool:
        """Compact if estimated tokens exceed budget."""
        return estimated_tokens > max_tokens

    def compact(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Compact with rolling summary.

        Strategy:
        1. Separate system messages (preserve at start)
        2. Separate recent N messages (preserve at end)
        3. Summarize middle messages via LLM
        4. Construct: [system] + [summary as SYSTEM] + [recent]

        Args:
            messages: Messages to compact
            max_tokens: Target budget (advisory; we aim to fit)

        Returns:
            Compacted messages and metadata
        """
        if not messages:
            return [], self._metadata(0, 0, 0, 0, "")

        # Separate leading system messages
        system_messages = []
        non_system_start = 0
        for i, msg in enumerate(messages):
            if self._get_role(msg) == "system":
                system_messages.append(msg)
                non_system_start = i + 1
            else:
                break

        non_system_messages = messages[non_system_start:]

        # If we have fewer non-system messages than the window, no need to summarize
        if len(non_system_messages) <= self.recent_window:
            return messages, self._metadata(
                tokens_before=self._estimate_tokens(messages),
                tokens_after=self._estimate_tokens(messages),
                messages_summarized=0,
                messages_retained=len(messages),
                summary="",
            )

        # Split non-system into middle (to summarize) and recent (to preserve)
        middle_messages = non_system_messages[: -self.recent_window]
        recent_messages = non_system_messages[-self.recent_window :]

        # Generate summary of middle messages
        summary_text = self._generate_summary(middle_messages)

        # Construct compacted history
        summary_message = {"role": "system", "content": f"**Conversation summary:**\n\n{summary_text}"}
        compacted = system_messages + [summary_message] + recent_messages

        metadata = self._metadata(
            tokens_before=self._estimate_tokens(messages),
            tokens_after=self._estimate_tokens(compacted),
            messages_summarized=len(middle_messages),
            messages_retained=len(system_messages) + 1 + len(recent_messages),  # +1 for summary
            summary=summary_text,
        )

        return compacted, metadata

    def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Generate LLM summary of messages.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return "(No messages to summarize)"

        # Format messages for prompt
        formatted_turns = []
        for i, msg in enumerate(messages, start=1):
            role = self._get_role(msg).upper()
            content = self._get_content(msg)
            formatted_turns.append(f"{role} turn {i}: {content}")

        turns_text = "\n\n".join(formatted_turns)
        prompt = f"{self.summary_prompt_template}\n\n{turns_text}"

        # Invoke LLM
        try:
            response = self.llm.invoke(prompt)
            # Handle different response formats
            if isinstance(response, str):
                return response.strip()
            elif hasattr(response, "content"):
                return str(response.content).strip()
            elif isinstance(response, dict):
                return str(response.get("content", str(response))).strip()
            return str(response).strip()
        except Exception as e:
            # Fallback if LLM call fails
            return f"(Summary generation failed: {str(e)})"

    @staticmethod
    def _get_role(message: Dict[str, Any]) -> str:
        """Extract role from message."""
        return str(message.get("role", "")).lower()

    @staticmethod
    def _get_content(message: Dict[str, Any]) -> str:
        """Extract content from message."""
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle multi-part content
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(str(part.get("text", str(part))))
                else:
                    parts.append(str(part))
            return " ".join(parts)
        return str(content)

    @staticmethod
    def _estimate_tokens(messages: List[Dict[str, Any]]) -> int:
        """Estimate token count using 4 chars/token heuristic."""
        total_chars = 0
        for msg in messages:
            content = RollingSummaryStrategy._get_content(msg)
            total_chars += len(content)
        return total_chars // 4

    @staticmethod
    def _metadata(
        tokens_before: int,
        tokens_after: int,
        messages_summarized: int,
        messages_retained: int,
        summary: str,
    ) -> Dict[str, Any]:
        """Construct compaction metadata."""
        return {
            "summary": summary,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "tokens_saved": tokens_before - tokens_after,
            "messages_summarized": messages_summarized,
            "messages_retained": messages_retained,
        }
