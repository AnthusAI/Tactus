"""
CLI control channel implementation.

Provides interactive command-line prompts for control loop interactions.
Uses Rich for formatting and the host channel pattern for interruptibility.
"""

import sys
import logging
from typing import Optional, Any
from datetime import datetime, timezone

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

from tactus.protocols.control import (
    ControlRequest,
    ControlRequestType,
    ControlOption,
    ChannelCapabilities,
)
from tactus.adapters.channels.host import HostControlChannel

logger = logging.getLogger(__name__)


def format_time_ago(timestamp: datetime) -> str:
    """Format datetime as human-readable time ago string."""
    now = datetime.now(timezone.utc)
    delta = (
        now - timestamp.replace(tzinfo=timezone.utc)
        if timestamp.tzinfo is None
        else now - timestamp
    )

    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''}"


class CLIControlChannel(HostControlChannel):
    """
    CLI-based control channel using Rich prompts.

    Provides interactive command-line prompts for approval, input,
    review, and escalation requests. Can be interrupted if another
    channel responds first.

    Example:
        channel = CLIControlChannel()
        await channel.initialize()
        result = await channel.send(request)
        # ... wait for response via receive() or cancellation
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize CLI control channel.

        Args:
            console: Rich Console instance (creates new one if not provided)
        """
        super().__init__()
        self.console = console or Console()

    @property
    def channel_id(self) -> str:
        """Return channel identifier."""
        return "cli"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """CLI supports all request types with immediate responses."""
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_interactive_buttons=False,
            supports_file_attachments=False,
            max_message_length=None,
            is_synchronous=True,
        )

    async def initialize(self) -> None:
        """Initialize the CLI channel."""
        logger.info("%s: initializing...", self.channel_id)
        # Check if stdin is a tty
        if not sys.stdin.isatty():
            logger.warning("%s: stdin is not a tty, prompts may not work", self.channel_id)
        logger.info("%s: ready", self.channel_id)

    def _display_request(self, request: ControlRequest) -> None:
        """
        Display the control request with rich formatting.

        Shows:
        - Procedure name and subject
        - Elapsed time
        - Input summary (if provided)
        - Prior interactions (if any)
        - The message and options

        Args:
            request: The control request to display
        """
        self.console.print()

        # Header: procedure name and subject
        header = f"[bold]{request.procedure_name}[/bold]"
        if request.subject:
            header += f": [cyan]{request.subject}[/cyan]"
        self.console.print(header)

        # Timing
        self.console.print(f"[dim]Started {format_time_ago(request.started_at)} ago[/dim]")

        # Input summary
        if request.input_summary:
            table = Table(title="Input Data", show_header=False, box=None)
            for key, value in request.input_summary.items():
                table.add_row(f"[dim]{key}:[/dim]", str(value))
            self.console.print(Panel(table, border_style="dim"))

        # Prior interactions
        if request.prior_interactions:
            self.console.print("\n[dim]Previous decisions:[/dim]")
            for interaction in request.prior_interactions:
                responder = interaction.responded_by or interaction.channel_id
                self.console.print(f"  [dim]•[/dim] {responder}: {interaction.response_value}")

        # The message
        self.console.print()
        self.console.print(
            Panel(
                request.message,
                title=f"[bold]{request.request_type.value.upper()}[/bold]",
                style="yellow",
            )
        )

    def _prompt_for_input(self, request: ControlRequest) -> Optional[Any]:
        """
        Collect input from the user via CLI prompt.

        Routes to appropriate handler based on request type.

        Args:
            request: The control request being handled

        Returns:
            The user's response value, or None if cancelled
        """
        if self.is_cancelled():
            return None

        request_type = request.request_type
        if request_type == ControlRequestType.APPROVAL:
            return self._handle_approval(request)
        if request_type == ControlRequestType.INPUT:
            return self._handle_input(request)
        if request_type == ControlRequestType.REVIEW:
            return self._handle_review(request)
        if request_type == ControlRequestType.ESCALATION:
            return self._handle_escalation(request)
        if request_type == ControlRequestType.INPUTS:
            return self._handle_inputs(request)
        else:
            # Default: treat as input
            return self._handle_input(request)

    def _handle_approval(self, request: ControlRequest) -> Optional[bool]:
        """Handle approval request."""
        if self.is_cancelled():
            return None

        default = request.default_value if request.default_value is not None else False

        try:
            approved = Confirm.ask("Approve?", default=default, console=self.console)
            return approved if not self.is_cancelled() else None
        except (EOFError, KeyboardInterrupt):
            return None

    def _handle_input(self, request: ControlRequest) -> Optional[Any]:
        """Handle input request."""
        if self.is_cancelled():
            return None

        default = str(request.default_value) if request.default_value is not None else None

        try:
            # Check if there are options
            if request.options:
                return self._handle_options(request.options, default)
            else:
                # Free-form input
                value = Prompt.ask("Enter value", default=default, console=self.console)
                return value if not self.is_cancelled() else None
        except (EOFError, KeyboardInterrupt):
            return None

    def _handle_options(
        self, options: list[ControlOption], default: Optional[str]
    ) -> Optional[Any]:
        """Handle options selection."""
        # Display options
        self.console.print("\n[bold]Options:[/bold]")
        for index, option in enumerate(options, 1):
            self.console.print(f"  {index}. [cyan]{option.label}[/cyan]")
            if option.description:
                self.console.print(f"     [dim]{option.description}[/dim]")

        # Get choice
        while not self.is_cancelled():
            try:
                choice_str = Prompt.ask(
                    "Select option (number)",
                    default=default,
                    console=self.console,
                )

                try:
                    choice = int(choice_str)
                    if 1 <= choice <= len(options):
                        return options[choice - 1].value
                    else:
                        self.console.print(f"[red]Invalid choice. Enter 1-{len(options)}[/red]")
                except ValueError:
                    self.console.print("[red]Invalid input. Enter a number[/red]")
            except (EOFError, KeyboardInterrupt):
                return None

        return None

    def _handle_review(self, request: ControlRequest) -> Optional[dict]:
        """Handle review request."""
        if self.is_cancelled():
            return None

        self.console.print("\n[bold]Review Options:[/bold]")
        self.console.print("  1. [green]Approve[/green] - Accept as-is")
        self.console.print("  2. [yellow]Edit[/yellow] - Provide changes")
        self.console.print("  3. [red]Reject[/red] - Reject and request redo")

        while not self.is_cancelled():
            try:
                choice = Prompt.ask(
                    "Your decision",
                    choices=["1", "2", "3", "approve", "edit", "reject"],
                    default="1",
                    console=self.console,
                )

                if self.is_cancelled():
                    return None

                if choice in ["1", "approve"]:
                    return {"decision": "approved", "feedback": None, "edited_artifact": None}
                elif choice in ["2", "edit"]:
                    feedback = Prompt.ask("What changes would you like?", console=self.console)
                    if self.is_cancelled():
                        return None
                    return {"decision": "approved", "feedback": feedback, "edited_artifact": None}
                elif choice in ["3", "reject"]:
                    feedback = Prompt.ask("Why are you rejecting?", console=self.console)
                    if self.is_cancelled():
                        return None
                    return {"decision": "rejected", "feedback": feedback, "edited_artifact": None}
            except (EOFError, KeyboardInterrupt):
                return None

        return None

    def _handle_escalation(self, request: ControlRequest) -> Optional[None]:
        """Handle escalation request (acknowledgment only)."""
        if self.is_cancelled():
            return None

        self.console.print("\n[yellow bold]⚠ This issue requires escalation[/yellow bold]")

        try:
            Confirm.ask(
                "Press Enter to acknowledge and continue",
                default=True,
                show_default=False,
                console=self.console,
            )
            return None if self.is_cancelled() else True
        except (EOFError, KeyboardInterrupt):
            return None

    def _handle_inputs(self, request: ControlRequest) -> Optional[dict]:
        """Handle batched inputs request (multiple inputs in one interaction)."""
        if self.is_cancelled():
            return None

        items = request.items or []

        if not items:
            self.console.print("[red]Error: No items found in inputs request[/red]")
            return {}

        # Display summary
        self.console.print(f"\n[bold cyan]Collecting {len(items)} inputs:[/bold cyan]")
        for index, item in enumerate(items, 1):
            req_marker = "*" if item.required else ""
            self.console.print(f"  {index}. [cyan]{item.label}[/cyan]{req_marker}")
        self.console.print()

        # Collect responses for each item
        responses = {}

        for index, item in enumerate(items, 1):
            if self.is_cancelled():
                return None

            # Display item panel
            self.console.print(
                Panel(
                    item.message,
                    title=f"[bold]{index}/{len(items)}: {item.label}[/bold]",
                    style="cyan" if item.required else "blue",
                )
            )

            # Handle based on item type
            try:
                value = None
                if item.request_type == ControlRequestType.APPROVAL:
                    default = item.default_value if item.default_value is not None else False
                    value = Confirm.ask("Approve?", default=default, console=self.console)

                elif item.request_type == ControlRequestType.INPUT:
                    placeholder = item.metadata.get("placeholder", "") if item.metadata else ""
                    multiline = item.metadata.get("multiline", False) if item.metadata else False

                    if multiline:
                        self.console.print("[dim](Enter text, press Ctrl+D when done)[/dim]")
                        lines = []
                        try:
                            while not self.is_cancelled():
                                line = Prompt.ask("", console=self.console, show_default=False)
                                lines.append(line)
                        except EOFError:
                            value = "\n".join(lines)
                    else:
                        prompt_text = "Enter value"
                        if placeholder:
                            prompt_text = f"{prompt_text} ({placeholder})"
                        default_str = (
                            str(item.default_value) if item.default_value is not None else None
                        )
                        value = Prompt.ask(prompt_text, default=default_str, console=self.console)

                elif item.request_type == ControlRequestType.SELECT:
                    # For now, use the simple options handler
                    # This could be enhanced to support metadata.mode = "multiple"
                    value = self._handle_options(item.options, item.default_value)

                elif item.request_type == ControlRequestType.REVIEW:
                    self.console.print("\n[bold]Review Options:[/bold]")
                    self.console.print("  1. [green]Approve[/green] - Accept as-is")
                    self.console.print("  2. [yellow]Edit[/yellow] - Provide changes")
                    self.console.print("  3. [red]Reject[/red] - Reject and request redo")

                    choice = Prompt.ask(
                        "Your decision",
                        choices=["1", "2", "3", "approve", "edit", "reject"],
                        default="1",
                        console=self.console,
                    )

                    if choice in ["1", "approve"]:
                        decision = "approved"
                        feedback = None
                    elif choice in ["2", "edit"]:
                        decision = "approved"
                        feedback = Prompt.ask("What changes would you like?", console=self.console)
                    else:  # reject
                        decision = "rejected"
                        feedback = Prompt.ask("Why are you rejecting?", console=self.console)

                    value = {"decision": decision, "feedback": feedback}

                else:
                    # Default to input
                    value = Prompt.ask("Enter value", console=self.console)

                # Store response if required or if value was provided
                if self.is_cancelled():
                    return None

                if item.required or value:
                    responses[item.item_id] = value

                self.console.print()  # Add spacing

            except (EOFError, KeyboardInterrupt):
                return None

        # Display summary
        if not self.is_cancelled():
            self.console.print("[bold green]✓ All inputs collected[/bold green]")
            self.console.print("\n[bold]Summary:[/bold]")
            for item_id, value in responses.items():
                item_label = next(
                    (item.label for item in items if item.item_id == item_id), item_id
                )
                value_str = (
                    str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value)
                )
                if len(value_str) > 60:
                    value_str = value_str[:57] + "..."
                self.console.print(f"  [cyan]{item_label}:[/cyan] {value_str}")

        return None if self.is_cancelled() else responses

    def _show_cancelled(self, reason: str) -> None:
        """
        Show cancellation message.

        Displays a green checkmark and the reason (typically
        "Responded via {channel}").

        Args:
            reason: Reason for cancellation
        """
        self.console.print(f"\n[green]✓ {reason}[/green]")


def is_cli_available() -> bool:
    """
    Check if CLI control channel is available.

    Returns True if stdin is a tty (interactive terminal).
    Used for auto-detection of whether to enable CLI channel.

    Returns:
        True if CLI is available, False otherwise
    """
    return sys.stdin.isatty()
