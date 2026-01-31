"""
CLI Log Handler for Rich-formatted logging.

Renders log events using Rich console for beautiful CLI output.
"""

import logging
from typing import Optional
from rich.console import Console

from tactus.protocols.models import LogEvent, CostEvent

logger = logging.getLogger(__name__)


class CLILogHandler:
    """
    CLI log handler using Rich formatting.

    Receives structured log events and renders them with Rich
    for beautiful console output.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize CLI log handler.

        Args:
            console: Rich Console instance (creates new one if not provided)
        """
        self.console = console or Console()
        self.cost_events = []  # Track cost events for aggregation
        logger.debug("CLILogHandler initialized")

    def log(self, event: LogEvent) -> None:
        """
        Render log event with Rich formatting.

        Args:
            event: Structured log event
        """
        # Handle stream chunks specially
        from tactus.protocols.models import AgentStreamChunkEvent

        if isinstance(event, AgentStreamChunkEvent):
            self._display_stream_chunk(event)
            return

        # Handle cost events specially
        if isinstance(event, CostEvent):
            self._display_cost_event(event)
            return

        # Handle agent turn events
        from tactus.protocols.models import AgentTurnEvent

        if isinstance(event, AgentTurnEvent):
            self._display_agent_turn_event(event)
            return

        # Handle tool call events
        from tactus.protocols.models import ToolCallEvent

        if isinstance(event, ToolCallEvent):
            self._display_tool_call_event(event)
            return

        # Handle checkpoint created events
        from tactus.protocols.models import CheckpointCreatedEvent

        if isinstance(event, CheckpointCreatedEvent):
            self._display_checkpoint_event(event)
            return

        # Handle ExecutionSummaryEvent specially
        if event.event_type == "execution_summary":
            self._display_execution_summary(event)
            return

        # Use Rich to format nicely for other events
        if hasattr(event, "context") and event.context:
            # Log with context formatted as part of the message
            import json

            context_str = json.dumps(event.context, indent=2)
            self.console.log(f"{event.message}\n{context_str}")
        else:
            # Simple log message
            self.console.log(event.message)

    def _display_stream_chunk(self, event) -> None:
        """Display streaming text chunk in real-time."""
        # Print chunk without newline so text flows naturally
        # Use markup=False to avoid interpreting Rich markup in the text
        self.console.print(event.chunk_text, end="", markup=False)

    def _display_agent_turn_event(self, event) -> None:
        """Display agent turn start/complete event."""

        if event.stage == "started":
            self.console.print(
                f"[blue]→ Agent[/blue] [bold]{event.agent_name}[/bold]: [blue]Waiting for response...[/blue]"
            )
        elif event.stage == "completed":
            # Add newline after streaming completes to separate from next output
            self.console.print()  # Newline after streamed text
            duration_str = f"{event.duration_ms:.0f}ms" if event.duration_ms else ""
            self.console.print(
                f"[green]✓ Agent[/green] [bold]{event.agent_name}[/bold]: [green]Completed[/green] {duration_str}"
            )

    def _display_tool_call_event(self, event) -> None:
        """Display tool call event."""
        import json

        # Format arguments compactly if they're simple
        args_str = ""
        if event.tool_args:
            # For simple args, show inline
            if len(event.tool_args) == 1 and len(str(event.tool_args)) < 60:
                args_str = f" {json.dumps(event.tool_args, default=str)}"
            else:
                # For complex args, show on next line
                args_str = f"\n  Args: {json.dumps(event.tool_args, indent=2, default=str)}"

        # Format result if available
        result_str = ""
        if event.tool_result is not None:
            result_text = str(event.tool_result)
            if len(result_text) < 60:
                result_str = f"\n  Result: {result_text}"
            else:
                # Truncate long results
                result_str = f"\n  Result: {result_text[:57]}..."

        duration_str = f" ({event.duration_ms:.0f}ms)" if event.duration_ms else ""

        self.console.print(
            f"[cyan]→ Tool[/cyan] [bold]{event.tool_name}[/bold]{args_str}{result_str}{duration_str}"
        )

    def _display_checkpoint_event(self, event) -> None:
        """Display checkpoint created event."""
        # Format checkpoint type (e.g., "agent_turn" -> "Agent Turn")
        type_display = event.checkpoint_type.replace("_", " ").title()

        # Format duration if available
        duration_str = f" ({event.duration_ms:.0f}ms)" if event.duration_ms else ""

        # Format source location if available
        location_str = ""
        if event.source_location:
            location_str = (
                f"\n  Location: {event.source_location.file}:{event.source_location.line}"
            )

        self.console.print(
            f"[yellow]• Checkpoint[/yellow] [bold]{event.checkpoint_position}[/bold]: {type_display}{duration_str}{location_str}"
        )

    def _display_cost_event(self, event: CostEvent) -> None:
        """Display cost event with comprehensive metrics."""
        # Track cost event for aggregation
        self.cost_events.append(event)

        # Primary metrics - always show
        self.console.print(
            f"[green]$ Cost[/green] [bold]{event.agent_name}[/bold]: "
            f"[green bold]${event.total_cost:.6f}[/green bold] "
            f"({event.total_tokens:,} tokens, {event.model}"
            f"{f', {event.duration_ms:.0f}ms' if event.duration_ms else ''})"
        )

        # Show retry warning if applicable
        if event.retry_count > 0:
            self.console.print(
                f"  [yellow]⚠ Retried {event.retry_count} time(s) due to validation[/yellow]"
            )

        # Show cache hit if applicable
        if event.cache_hit and event.cache_tokens:
            self.console.print(
                f"  [green]✓ Cache hit: {event.cache_tokens:,} tokens"
                f"{f' (saved ${event.cache_cost:.6f})' if event.cache_cost else ''}[/green]"
            )

    def _display_execution_summary(self, event) -> None:
        """Display execution summary with cost breakdown."""
        self.console.print(
            f"\n[green bold]✓ Procedure completed[/green bold]: "
            f"{event.iterations} iterations, {len(event.tools_used)} tools used"
        )

        # Display cost summary if costs were incurred
        if hasattr(event, "total_cost") and event.total_cost > 0:
            self.console.print("\n[green bold]$ Cost Summary[/green bold]")
            self.console.print(f"  Total Cost: [green bold]${event.total_cost:.6f}[/green bold]")
            self.console.print(f"  Total Tokens: {event.total_tokens:,}")

            if hasattr(event, "cost_breakdown") and event.cost_breakdown:
                self.console.print("\n  [bold]Per-call breakdown:[/bold]")
                for cost in event.cost_breakdown:
                    self.console.print(
                        f"    {cost.agent_name}: ${cost.total_cost:.6f} "
                        f"({cost.total_tokens:,} tokens, {cost.duration_ms:.0f}ms)"
                    )

        # Display checkpoint summary if checkpoints were created
        if hasattr(event, "checkpoint_count") and event.checkpoint_count > 0:
            self.console.print("\n[yellow bold]• Checkpoint Summary[/yellow bold]")
            self.console.print(f"  Total Checkpoints: {event.checkpoint_count}")

            if hasattr(event, "checkpoint_types") and event.checkpoint_types:
                self.console.print("  Types:")
                for checkpoint_type, count in sorted(event.checkpoint_types.items()):
                    type_display = checkpoint_type.replace("_", " ").title()
                    self.console.print(f"    {type_display}: {count}")

            if hasattr(event, "checkpoint_duration_ms") and event.checkpoint_duration_ms:
                avg_duration = event.checkpoint_duration_ms / event.checkpoint_count
                total_seconds = event.checkpoint_duration_ms / 1000
                self.console.print(f"  Average Duration: {avg_duration:.0f}ms")
                self.console.print(f"  Total Duration: {total_seconds:.1f}s")
