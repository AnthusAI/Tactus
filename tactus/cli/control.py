"""
Tactus Control CLI - Connect to running procedure and respond to control requests.

This is a standalone CLI application that connects to the runtime's IPC socket
and allows humans (or other controllers) to respond to control requests from
running procedures.

Usage:
    tactus control [--socket PATH]
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tactus.broker.protocol import read_message, write_message

logger = logging.getLogger(__name__)


class ControlCLI:
    """CLI app for responding to control requests via IPC."""

    def __init__(
        self, socket_path: str = "/tmp/tactus-control.sock", auto_respond: Optional[str] = None
    ):
        """
        Initialize control CLI.

        Args:
            socket_path: Path to runtime's Unix socket
            auto_respond: If set, automatically respond with this value (for testing)
        """
        self.socket_path = socket_path
        self.auto_respond = auto_respond
        self.console = Console()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False

    async def connect(self) -> bool:
        """
        Connect to runtime's IPC socket.

        Returns:
            True if connected successfully
        """
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
            return True
        except FileNotFoundError:
            self.console.print(f"[red]✗ Socket not found: {self.socket_path}[/red]")
            self.console.print("\n[yellow]Is the Tactus runtime running?[/yellow]")
            return False
        except ConnectionRefusedError:
            self.console.print(f"[red]✗ Connection refused: {self.socket_path}[/red]")
            return False
        except Exception as e:
            self.console.print(f"[red]✗ Failed to connect: {e}[/red]")
            return False

    async def disconnect(self) -> None:
        """Close connection to runtime."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    async def watch_mode(self) -> None:
        """
        Interactive mode - watch for requests and respond.

        This is the main entry point for the control CLI. It connects to the
        runtime, displays pending requests, and prompts for responses.
        """
        # Connect to runtime
        if not await self.connect():
            return

        self.console.print()
        self.console.print(
            Panel(
                f"[green]Connected to: {self.socket_path}[/green]\n"
                "[dim]Waiting for control requests...[/dim]",
                title="Control Session",
                border_style="green",
            )
        )
        self.console.print()

        self._running = True

        try:
            # Read messages from runtime
            while self._running:
                try:
                    message = await read_message(self._reader)
                except asyncio.IncompleteReadError:
                    self.console.print("\n[yellow]✗ Connection closed by runtime[/yellow]")
                    break
                except EOFError:
                    self.console.print("\n[yellow]✗ Connection closed by runtime[/yellow]")
                    break

                await self._handle_message(message)

        except KeyboardInterrupt:
            self.console.print("\n[dim]Disconnecting...[/dim]")

        finally:
            await self.disconnect()

    async def _handle_message(self, message: Dict) -> None:
        """
        Handle a message from the runtime.

        Args:
            message: Parsed JSON message
        """
        msg_type = message.get("type")

        if msg_type == "control.request":
            await self._handle_request(message)

        elif msg_type == "control.cancelled":
            self._handle_cancellation(message)

        elif msg_type == "control.list_response":
            self._handle_list_response(message)

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_request(self, request: Dict) -> None:
        """
        Handle a control request from the runtime.

        Args:
            request: Control request message
        """
        request_id = request["request_id"]
        procedure_name = request.get("procedure_name", "Unknown Procedure")
        request_type = request["request_type"]
        message = request["message"]
        options = request.get("options", [])
        default_value = request.get("default_value")
        started_at = request.get("started_at")

        # Calculate elapsed time
        elapsed_str = "Unknown"
        if started_at:
            started = datetime.fromisoformat(started_at)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if elapsed < 60:
                elapsed_str = f"{int(elapsed)} seconds ago"
            elif elapsed < 3600:
                elapsed_str = f"{int(elapsed / 60)} minutes ago"
            else:
                elapsed_str = f"{int(elapsed / 3600)} hours ago"

        # Display request panel
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]{procedure_name}[/bold]\n" f"Started: {elapsed_str}",
                title="Control Request",
                border_style="blue",
            )
        )
        self.console.print()

        self.console.print(
            Panel(
                f"[bold]{message}[/bold]\n\n"
                f"Type: {request_type}\n"
                f"ID: [dim]{request_id}[/dim]",
                border_style="cyan",
            )
        )
        self.console.print()

        # Handle based on request type
        if request_type == "approval":
            await self._handle_approval_request(request, options, default_value)

        elif request_type == "choice":
            await self._handle_choice_request(request, options, default_value)

        elif request_type == "input":
            await self._handle_input_request(request, default_value)

        else:
            self.console.print(f"[yellow]⚠ Unknown request type: {request_type}[/yellow]")

    async def _handle_approval_request(
        self, request: Dict, options: List[Dict], default_value: Optional[bool]
    ) -> None:
        """Handle an approval request."""
        request_id = request["request_id"]

        # Auto-respond mode (for testing)
        if self.auto_respond is not None:
            value = self.auto_respond.lower() in ("y", "yes", "true", "1")
            await self._send_response(request_id, value)
            return

        # Interactive prompt
        if default_value is not None:
            prompt_str = f"Approve? [y/n] ({default_value and 'y' or 'n'}): "
        else:
            prompt_str = "Approve? [y/n]: "

        response = Confirm.ask(
            prompt_str, default=default_value if default_value is not None else None
        )
        await self._send_response(request_id, response)

    async def _handle_choice_request(
        self, request: Dict, options: List[Dict], default_value: Optional[any]
    ) -> None:
        """Handle a choice request."""
        request_id = request["request_id"]

        # Auto-respond mode (for testing)
        if self.auto_respond is not None:
            # Try to match auto_respond to an option value
            for option in options:
                if str(option.get("value")) == self.auto_respond:
                    await self._send_response(request_id, option["value"])
                    return
            # Default to first option
            await self._send_response(request_id, options[0]["value"] if options else None)
            return

        # Display options
        self.console.print("Options:")
        for i, option in enumerate(options, 1):
            label = option.get("label", str(option.get("value")))
            value = option.get("value")
            if value == default_value:
                self.console.print(f"  [{i}] {label} [dim](default)[/dim]")
            else:
                self.console.print(f"  [{i}] {label}")

        self.console.print()

        # Prompt for selection
        while True:
            selection = Prompt.ask(
                "Choose an option",
                default=(
                    str(
                        options.index(
                            next(
                                (o for o in options if o.get("value") == default_value), options[0]
                            )
                        )
                        + 1
                    )
                    if default_value
                    else "1"
                ),
            )
            try:
                index = int(selection) - 1
                if 0 <= index < len(options):
                    value = options[index]["value"]
                    await self._send_response(request_id, value)
                    break
                else:
                    self.console.print("[red]Invalid selection, please try again[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number[/red]")

    async def _handle_input_request(self, request: Dict, default_value: Optional[str]) -> None:
        """Handle a text input request."""
        request_id = request["request_id"]

        # Auto-respond mode (for testing)
        if self.auto_respond is not None:
            await self._send_response(request_id, self.auto_respond)
            return

        # Interactive prompt
        response = Prompt.ask("Enter value", default=default_value or "")
        await self._send_response(request_id, response)

    async def _send_response(self, request_id: str, value: any) -> None:
        """
        Send a response back to the runtime.

        Args:
            request_id: Request being responded to
            value: Response value
        """
        response_message = {
            "type": "control.response",
            "request_id": request_id,
            "value": value,
            "responder_id": "control-cli",
            "responded_at": datetime.now().isoformat(),
        }

        try:
            await write_message(self._writer, response_message)
            self.console.print()
            self.console.print("[green]✓ Response sent via IPC[/green]")
            self.console.print()
        except Exception as e:
            self.console.print(f"[red]✗ Failed to send response: {e}[/red]")

    def _handle_cancellation(self, message: Dict) -> None:
        """Handle a cancellation notification."""
        request_id = message["request_id"]
        reason = message.get("reason", "unknown")
        self.console.print()
        self.console.print(f"[yellow]✗ Request {request_id} was cancelled: {reason}[/yellow]")
        self.console.print()

    def _handle_list_response(self, message: Dict) -> None:
        """Handle a list response."""
        requests = message.get("requests", [])

        if not requests:
            self.console.print("[dim]No pending requests[/dim]")
            return

        table = Table(title="Pending Requests")
        table.add_column("ID", style="cyan")
        table.add_column("Procedure", style="green")
        table.add_column("Type")
        table.add_column("Message")

        for request in requests:
            table.add_row(
                request["request_id"][:8],
                request.get("procedure_name", "Unknown"),
                request["request_type"],
                request["message"][:50] + ("..." if len(request["message"]) > 50 else ""),
            )

        self.console.print(table)

    async def list_requests(self) -> None:
        """Request a list of pending requests from the runtime."""
        if not await self.connect():
            return

        try:
            # Send list request
            list_message = {"type": "control.list"}
            await write_message(self._writer, list_message)

            # Wait for response
            message = await read_message(self._reader)
            if message.get("type") == "control.list_response":
                self._handle_list_response(message)

        except Exception as e:
            self.console.print(f"[red]✗ Failed to list requests: {e}[/red]")

        finally:
            await self.disconnect()


async def main(socket_path: str = "/tmp/tactus-control.sock", auto_respond: Optional[str] = None):
    """
    Main entry point for control CLI.

    Args:
        socket_path: Path to runtime's Unix socket
        auto_respond: If set, automatically respond with this value
    """
    cli = ControlCLI(socket_path, auto_respond)
    await cli.watch_mode()


if __name__ == "__main__":
    import sys

    socket_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/tactus-control.sock"
    auto_respond = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(main(socket_path, auto_respond))
