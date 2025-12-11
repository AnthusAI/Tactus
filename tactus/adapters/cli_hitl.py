"""
CLI HITL Handler for interactive human-in-the-loop interactions.

Provides interactive prompts for approval, input, review, and escalation.
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
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize CLI HITL handler.

        Args:
            console: Rich Console instance (creates new one if not provided)
        """
        self.console = console or Console()
        logger.info("CLIHITLHandler initialized")

    def request_interaction(self, procedure_id: str, request: HITLRequest) -> HITLResponse:
        """
        Request human interaction via CLI prompt.

        Args:
            procedure_id: Procedure ID
            request: HITLRequest with interaction details

        Returns:
            HITLResponse with user's response
        """
        logger.info(f"HITL request: {request.request_type} - {request.message}")

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
            for i, option in enumerate(request.options, 1):
                label = option.get("label", f"Option {i}")
                description = option.get("description", "")
                self.console.print(f"  {i}. [cyan]{label}[/cyan]")
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

    def check_pending_response(self, procedure_id: str, message_id: str) -> Optional[HITLResponse]:
        """
        Check for pending response (not used in CLI mode).

        In CLI mode, interactions are synchronous, so this always returns None.
        """
        return None

    def cancel_pending_request(self, procedure_id: str, message_id: str) -> None:
        """
        Cancel pending request (not used in CLI mode).

        In CLI mode, interactions are synchronous, so this is a no-op.
        """
        pass
