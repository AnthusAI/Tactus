"""
CLI HITL Handler for interactive human-in-the-loop interactions.

This module provides backward compatibility with the existing HITLHandler protocol
while the new control loop architecture is being developed.

For new code, prefer using the ControlLoopHandler and CLIControlChannel classes
from the control loop module.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from tactus.protocols.models import HITLRequest, HITLResponse

logger = logging.getLogger(__name__)


class CLIHITLHandler:
    """
    CLI-based HITL handler using rich prompts.

    Provides interactive command-line prompts for human-in-the-loop interactions.

    Note: This class is maintained for backward compatibility. For new implementations,
    consider using ControlLoopHandler with CLIControlChannel which supports:
    - Multi-channel racing (first response wins)
    - Interruptible prompts
    - Namespace-based routing
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize CLI HITL handler.

        Args:
            console: Rich Console instance (creates new one if not provided)
        """
        self.console = console or Console()
        logger.debug("CLIHITLHandler initialized")

    def request_interaction(self, procedure_id: str, request: HITLRequest) -> HITLResponse:
        """
        Request human interaction via CLI prompt.

        Args:
            procedure_id: Procedure ID
            request: HITLRequest with interaction details

        Returns:
            HITLResponse with user's response
        """
        logger.debug("HITL request: %s - %s", request.request_type, request.message)

        # Display the request in a panel
        self.console.print()
        self.console.print(
            Panel(
                request.message,
                title=f"[bold]{request.request_type.upper()}[/bold]",
                style="yellow",
            )
        )

        # Handle based on request type
        if request.request_type == "approval":
            return self._handle_approval(request)
        elif request.request_type == "input":
            return self._handle_input(request)
        elif request.request_type == "review":
            return self._handle_review(request)
        elif request.request_type == "escalation":
            return self._handle_escalation(request)
        elif request.request_type == "inputs":
            return self._handle_inputs(request)
        else:
            # Default: treat as input
            return self._handle_input(request)

    def _handle_approval(self, request: HITLRequest) -> HITLResponse:
        """Handle approval request."""
        default = request.default_value if request.default_value is not None else False

        # Use rich Confirm for yes/no
        approved = Confirm.ask("Approve?", default=default, console=self.console)

        return HITLResponse(
            value=approved, responded_at=datetime.now(timezone.utc), timed_out=False
        )

    def _handle_input(self, request: HITLRequest) -> HITLResponse:
        """Handle input request."""
        default = str(request.default_value) if request.default_value is not None else None

        # Check if there are options
        if request.options:
            # Display options
            self.console.print("\n[bold]Options:[/bold]")
            for index, option in enumerate(request.options, 1):
                label = option.get("label", f"Option {index}")
                description = option.get("description", "")
                self.console.print(f"  {index}. [cyan]{label}[/cyan]")
                if description:
                    self.console.print(f"     [dim]{description}[/dim]")

            # Get choice
            while True:
                choice_str = Prompt.ask(
                    "Select option (number)", default=default, console=self.console
                )

                try:
                    choice = int(choice_str)
                    if 1 <= choice <= len(request.options):
                        selected = request.options[choice - 1]
                        value = selected.get("value", selected.get("label"))
                        break
                    else:
                        self.console.print(
                            f"[red]Invalid choice. Enter 1-{len(request.options)}[/red]"
                        )
                except ValueError:
                    self.console.print("[red]Invalid input. Enter a number[/red]")

        else:
            # Free-form input
            value = Prompt.ask("Enter value", default=default, console=self.console)

        return HITLResponse(value=value, responded_at=datetime.now(timezone.utc), timed_out=False)

    def _handle_review(self, request: HITLRequest) -> HITLResponse:
        """Handle review request."""
        self.console.print("\n[bold]Review Options:[/bold]")
        self.console.print("  1. [green]Approve[/green] - Accept as-is")
        self.console.print("  2. [yellow]Edit[/yellow] - Provide changes")
        self.console.print("  3. [red]Reject[/red] - Reject and request redo")

        while True:
            choice = Prompt.ask(
                "Your decision",
                choices=["1", "2", "3", "approve", "edit", "reject"],
                default="1",
                console=self.console,
            )

            if choice in ["1", "approve"]:
                decision = "approved"
                feedback = None
                edited_artifact = None
                break
            elif choice in ["2", "edit"]:
                decision = "approved"
                feedback = Prompt.ask("What changes would you like?", console=self.console)
                # In CLI, we can't easily edit artifacts, so just provide feedback
                edited_artifact = None
                break
            elif choice in ["3", "reject"]:
                decision = "rejected"
                feedback = Prompt.ask("Why are you rejecting?", console=self.console)
                edited_artifact = None
                break

        value = {"decision": decision, "feedback": feedback, "edited_artifact": edited_artifact}

        return HITLResponse(value=value, responded_at=datetime.now(timezone.utc), timed_out=False)

    def _handle_escalation(self, request: HITLRequest) -> HITLResponse:
        """Handle escalation request."""
        self.console.print("\n[yellow bold]⚠ This issue requires escalation[/yellow bold]")

        # Wait for acknowledgment
        Confirm.ask(
            "Press Enter to acknowledge and continue",
            default=True,
            show_default=False,
            console=self.console,
        )

        # Escalation doesn't need a specific value
        return HITLResponse(value=None, responded_at=datetime.now(timezone.utc), timed_out=False)

    def _handle_inputs(self, request: HITLRequest) -> HITLResponse:
        """Handle batched inputs request (multiple inputs in one interaction)."""
        # Extract items from metadata
        items = request.metadata.get("items", [])

        if not items:
            self.console.print("[red]Error: No items found in inputs request[/red]")
            return HITLResponse(value={}, responded_at=datetime.now(timezone.utc), timed_out=False)

        # Display summary
        self.console.print(f"\n[bold cyan]Collecting {len(items)} inputs:[/bold cyan]")
        for index, item in enumerate(items, 1):
            label = item.get("label", f"Item {index}")
            required = item.get("required", True)
            req_marker = "*" if required else ""
            self.console.print(f"  {index}. [cyan]{label}[/cyan]{req_marker}")
        self.console.print()

        # Collect responses for each item
        responses = {}

        for index, item in enumerate(items, 1):
            item_id = item.get("item_id")
            label = item.get("label", f"Item {index}")
            request_type = item.get("request_type", "input")
            message = item.get("message", "")
            required = item.get("required", True)
            options = item.get("options", [])
            default_value = item.get("default_value")
            metadata = item.get("metadata", {})

            # Display item panel
            self.console.print(
                Panel(
                    message,
                    title=f"[bold]{index}/{len(items)}: {label}[/bold]",
                    style="cyan" if required else "blue",
                )
            )

            # Handle based on item type
            if request_type == "approval":
                default = default_value if default_value is not None else False
                value = Confirm.ask("Approve?", default=default, console=self.console)

            elif request_type == "select":
                mode = metadata.get("mode", "single")

                if mode == "multiple":
                    # Multiple selection
                    self.console.print(
                        "\n[bold]Select multiple options (comma-separated numbers):[/bold]"
                    )
                    for index, option in enumerate(options, 1):
                        label_text = (
                            option.get("label", f"Option {index}")
                            if isinstance(option, dict)
                            else option
                        )
                        self.console.print(f"  {index}. [cyan]{label_text}[/cyan]")

                    min_selections = metadata.get("min", 0)
                    max_selections = metadata.get("max", len(options))

                    while True:
                        choice_str = Prompt.ask(
                            "Select options (e.g., 1,3,4)", console=self.console
                        )

                        try:
                            choices = [int(c.strip()) for c in choice_str.split(",")]
                            if all(1 <= c <= len(options) for c in choices):
                                if len(choices) < min_selections:
                                    self.console.print(
                                        f"[red]Select at least {min_selections} options[/red]"
                                    )
                                    continue
                                if len(choices) > max_selections:
                                    self.console.print(
                                        f"[red]Select at most {max_selections} options[/red]"
                                    )
                                    continue

                                # Get values for selected options
                                selected_values = []
                                for choice in choices:
                                    opt = options[choice - 1]
                                    if isinstance(opt, dict):
                                        selected_values.append(opt.get("value", opt.get("label")))
                                    else:
                                        selected_values.append(opt)
                                value = selected_values
                                break
                            else:
                                self.console.print(
                                    f"[red]Invalid choice. Enter 1-{len(options)}[/red]"
                                )
                        except ValueError:
                            self.console.print(
                                "[red]Invalid input. Enter comma-separated numbers[/red]"
                            )
                else:
                    # Single selection
                    self.console.print("\n[bold]Options:[/bold]")
                    for index, option in enumerate(options, 1):
                        if isinstance(option, dict):
                            label_text = option.get("label", f"Option {index}")
                            description = option.get("description", "")
                            self.console.print(f"  {index}. [cyan]{label_text}[/cyan]")
                            if description:
                                self.console.print(f"     [dim]{description}[/dim]")
                        else:
                            self.console.print(f"  {index}. [cyan]{option}[/cyan]")

                    while True:
                        choice_str = Prompt.ask("Select option (number)", console=self.console)

                        try:
                            choice = int(choice_str)
                            if 1 <= choice <= len(options):
                                selected = options[choice - 1]
                                if isinstance(selected, dict):
                                    value = selected.get("value", selected.get("label"))
                                else:
                                    value = selected
                                break
                            else:
                                self.console.print(
                                    f"[red]Invalid choice. Enter 1-{len(options)}[/red]"
                                )
                        except ValueError:
                            self.console.print("[red]Invalid input. Enter a number[/red]")

            elif request_type == "review":
                self.console.print("\n[bold]Review Options:[/bold]")
                self.console.print("  1. [green]Approve[/green] - Accept as-is")
                self.console.print("  2. [yellow]Edit[/yellow] - Provide changes")
                self.console.print("  3. [red]Reject[/red] - Reject and request redo")

                while True:
                    choice = Prompt.ask(
                        "Your decision",
                        choices=["1", "2", "3", "approve", "edit", "reject"],
                        default="1",
                        console=self.console,
                    )

                    if choice in ["1", "approve"]:
                        decision = "approved"
                        feedback = None
                        break
                    elif choice in ["2", "edit"]:
                        decision = "approved"
                        feedback = Prompt.ask("What changes would you like?", console=self.console)
                        break
                    elif choice in ["3", "reject"]:
                        decision = "rejected"
                        feedback = Prompt.ask("Why are you rejecting?", console=self.console)
                        break

                value = {"decision": decision, "feedback": feedback}

            else:
                # Default: input type
                placeholder = metadata.get("placeholder", "")
                multiline = metadata.get("multiline", False)

                if multiline:
                    self.console.print("[dim](Enter text, press Ctrl+D when done)[/dim]")
                    lines = []
                    try:
                        while True:
                            line = Prompt.ask("", console=self.console, show_default=False)
                            lines.append(line)
                    except EOFError:
                        value = "\n".join(lines)
                else:
                    prompt_text = "Enter value"
                    if placeholder:
                        prompt_text = f"{prompt_text} ({placeholder})"

                    default_str = str(default_value) if default_value is not None else None
                    value = Prompt.ask(prompt_text, default=default_str, console=self.console)

            # Store response if required or if value was provided
            if required or value:
                responses[item_id] = value

            self.console.print()  # Add spacing between items

        # Display summary
        self.console.print("[bold green]✓ All inputs collected[/bold green]")
        self.console.print("\n[bold]Summary:[/bold]")
        for item_id, value in responses.items():
            # Find the label for this item_id
            item_label = next(
                (item.get("label", item_id) for item in items if item.get("item_id") == item_id),
                item_id,
            )
            value_str = (
                str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value)
            )
            if len(value_str) > 60:
                value_str = value_str[:57] + "..."
            self.console.print(f"  [cyan]{item_label}:[/cyan] {value_str}")

        return HITLResponse(
            value=responses, responded_at=datetime.now(timezone.utc), timed_out=False
        )

    def check_pending_response(self, procedure_id: str, request_id: str) -> Optional[HITLResponse]:
        """
        Check for pending response (not used in CLI mode).

        In CLI mode, interactions are synchronous, so this always returns None.
        """
        return None

    def cancel_pending_request(self, procedure_id: str, request_id: str) -> None:
        """
        Cancel pending request (not used in CLI mode).

        In CLI mode, interactions are synchronous, so this is a no-op.
        """
        pass
