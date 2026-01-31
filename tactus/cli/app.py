"""
Tactus CLI Application.

Main entry point for the Tactus command-line interface.
Provides commands for running, validating, and testing workflows.
"""

# Disable Pydantic plugins for PyInstaller builds
# This prevents logfire (and other plugins) from being loaded via Pydantic's plugin system
# which causes errors when trying to inspect source code in frozen apps
import os

os.environ["PYDANTIC_DISABLE_PLUGINS"] = "1"

import asyncio
import json
from pathlib import Path
from typing import Any, Optional
import logging
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from tactus.core import TactusRuntime
from tactus.core.yaml_parser import ProcedureYAMLParser, ProcedureConfigError
from tactus.validation import TactusValidator, ValidationMode
from tactus.formatting import TactusFormatter, FormattingError
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage

# Setup rich console for pretty output
console = Console()

# Create Typer app
app = typer.Typer(
    name="tactus", help="Tactus - Workflow automation with Lua DSL", add_completion=False
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        is_eager=True,
    ),
):
    """Tactus CLI callback for global options."""
    if version:
        from tactus import __version__

        console.print(f"Tactus version: [bold]{__version__}[/bold]")
        raise typer.Exit()

    # If no subcommand was invoked and version flag not set, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


def load_tactus_config():
    """
    Load Tactus configuration from standard config locations.

    Loads (lowest to highest precedence):
    - system config (e.g. /etc/tactus/config.yml)
    - user config (e.g. ~/.tactus/config.yml)
    - project config (./.tactus/config.yml)

    Environment variables always win over config files (we only set vars that don't already exist).

    Returns:
        dict: Configuration dictionary, or empty dict if no config found
    """
    try:
        from tactus.core.config_manager import ConfigManager
        import json

        config_mgr = ConfigManager()

        configs = []
        for system_path in config_mgr._get_system_config_paths():
            if system_path.exists():
                cfg = config_mgr._load_yaml_file(system_path)
                if cfg:
                    configs.append(cfg)

        for user_path in config_mgr._get_user_config_paths():
            if user_path.exists():
                cfg = config_mgr._load_yaml_file(user_path)
                if cfg:
                    configs.append(cfg)

        project_path = Path.cwd() / ".tactus" / "config.yml"
        if project_path.exists():
            cfg = config_mgr._load_yaml_file(project_path)
            if cfg:
                configs.append(cfg)

        merged = config_mgr._merge_configs(configs) if configs else {}

        # Only set env vars that were not already set by the user/process.
        existing_env = set(os.environ.keys())

        for key, value in merged.items():
            if key == "mcp_servers":
                continue

            if isinstance(value, (str, int, float, bool)):
                env_key = key.upper()
                if env_key not in existing_env:
                    os.environ[env_key] = str(value)
            elif isinstance(value, list):
                env_key = key.upper()
                if env_key not in existing_env:
                    os.environ[env_key] = json.dumps(value)
            elif isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, (str, int, float, bool)):
                        env_key = f"{key.upper()}_{nested_key.upper()}"
                        if env_key not in existing_env:
                            os.environ[env_key] = str(nested_value)

        return merged
    except Exception as e:
        logging.debug(f"Could not load Tactus config: {e}")
        return {}


_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_LOG_FORMATS = {"rich", "terminal", "raw"}


class _TerminalLogHandler(logging.Handler):
    """Minimal, high-signal terminal logger (no timestamps/levels)."""

    def __init__(self, console: Console):
        super().__init__()
        self._console = console
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)

            # Make procedure-level logs the most prominent.
            if record.name.startswith("procedure"):
                style = "bold"
            elif record.levelno >= logging.ERROR:
                style = "bold red"
            elif record.levelno >= logging.WARNING:
                style = "yellow"
            elif record.levelno <= logging.DEBUG:
                style = "dim"
            else:
                style = ""

            self._console.print(message, style=style, markup=False, highlight=False)
        except Exception:
            self.handleError(record)


def setup_logging(
    verbose: bool = False,
    log_level: Optional[str] = None,
    log_format: str = "rich",
) -> None:
    """Setup CLI logging (level + format)."""
    if log_level is None:
        level = logging.DEBUG if verbose else logging.INFO
    else:
        key = str(log_level).strip().lower()
        if key not in _LOG_LEVELS:
            raise typer.BadParameter(
                f"Invalid --log-level '{log_level}'. "
                f"Use one of: {', '.join(sorted(_LOG_LEVELS.keys()))}"
            )
        level = _LOG_LEVELS[key]

    fmt = (log_format or "rich").strip().lower()
    if fmt not in _LOG_FORMATS:
        raise typer.BadParameter(
            f"Invalid --log-format '{log_format}'. Use one of: {', '.join(sorted(_LOG_FORMATS))}"
        )

    # Default: rich logs (group repeated timestamps).
    if fmt == "rich":
        handler: logging.Handler = RichHandler(
            console=console,
            show_path=False,
            rich_tracebacks=True,
            omit_repeated_times=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.basicConfig(level=level, format="%(message)s", handlers=[handler], force=True)
        return

    # Raw logs: one line per entry, CloudWatch-friendly.
    if fmt == "raw":
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(level=level, handlers=[handler], force=True)
        return

    # Terminal logs: no timestamps/levels, color by signal.
    handler = _TerminalLogHandler(console)
    logging.basicConfig(level=level, handlers=[handler], force=True)


def _parse_value(value_str: str, field_type: str) -> Any:
    """
    Parse a string value into the appropriate type.

    Args:
        value_str: The string value to parse
        field_type: The expected type (string, number, boolean, array, object)

    Returns:
        The parsed value in the appropriate type
    """
    if field_type == "boolean":
        return value_str.lower() in ("true", "yes", "1", "y")
    elif field_type == "number":
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return 0
    elif field_type == "array":
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            # Try to parse as comma-separated values
            if value_str.strip():
                return [v.strip() for v in value_str.split(",")]
            return []
    elif field_type == "object":
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            return {}
    else:
        return value_str


def _prompt_for_inputs(console: Console, input_schema: dict, provided_params: dict) -> dict:
    """
    Interactively prompt user for procedure inputs.

    Displays all inputs with their types, descriptions, and defaults,
    then prompts the user to confirm or modify each value.

    Args:
        console: Rich Console for output
        input_schema: Dict of input name -> field definition
        provided_params: Already provided --param values

    Returns:
        Dict of resolved input values
    """
    if not input_schema:
        return provided_params.copy()

    console.print(Panel("[bold]Procedure Inputs[/bold]", style="blue"))

    # Display input schema summary
    table = Table(title="Input Parameters")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Required", style="yellow")
    table.add_column("Default", style="green")
    table.add_column("Current", style="blue")

    for name, field in input_schema.items():
        required = "Yes" if field.get("required") else "No"
        default = str(field.get("default", "-")) if field.get("default") is not None else "-"
        current = str(provided_params.get(name, "-")) if name in provided_params else "-"
        table.add_row(name, field.get("type", "string"), required, default, current)

    console.print(table)
    console.print()

    # Prompt for each input
    resolved = {}
    for name, field in input_schema.items():
        field_type = field.get("type", "string")
        description = field.get("description", "")
        required = field.get("required", False)
        enum_values = field.get("enum")

        # Determine current value (provided > default)
        if name in provided_params:
            current_value = provided_params[name]
        elif field.get("default") is not None:
            current_value = field.get("default")
        else:
            current_value = None

        # Build prompt message
        prompt_msg = f"[cyan]{name}[/cyan]"
        if description:
            prompt_msg += f" [dim]({description})[/dim]"
        if required:
            prompt_msg += " [yellow]*[/yellow]"

        # Handle different types
        if field_type == "boolean":
            default_bool = bool(current_value) if current_value is not None else False
            value = Confirm.ask(prompt_msg, default=default_bool, console=console)

        elif enum_values and isinstance(enum_values, list):
            # Show enum options
            console.print(f"\n{prompt_msg}")
            console.print("[dim]Options:[/dim]")
            for i, opt in enumerate(enum_values, 1):
                console.print(f"  {i}. [cyan]{opt}[/cyan]")

            # Find default index
            default_idx = "1"
            if current_value in enum_values:
                default_idx = str(enum_values.index(current_value) + 1)

            while True:
                choice_str = Prompt.ask(
                    "Select option (number or value)",
                    default=default_idx,
                    console=console,
                )
                # Try as number first
                try:
                    choice = int(choice_str)
                    if 1 <= choice <= len(enum_values):
                        value = enum_values[choice - 1]
                        break
                except ValueError:
                    # Try as direct value
                    if choice_str in enum_values:
                        value = choice_str
                        break
                console.print(
                    f"[red]Invalid choice. Enter 1-{len(enum_values)} or a valid option.[/red]"
                )

        elif field_type == "array":
            # Format default as JSON string
            if isinstance(current_value, list):
                default_str = json.dumps(current_value)
            elif current_value is not None:
                default_str = str(current_value)
            else:
                default_str = "[]"

            console.print(f"\n{prompt_msg}")
            console.print("[dim]Enter JSON array (e.g., [1, 2, 3]) or comma-separated values[/dim]")
            value_str = Prompt.ask("Value", default=default_str, console=console)
            value = _parse_value(value_str, "array")

        elif field_type == "object":
            # Format default as JSON string
            if isinstance(current_value, dict):
                default_str = json.dumps(current_value)
            elif current_value is not None:
                default_str = str(current_value)
            else:
                default_str = "{}"

            console.print(f"\n{prompt_msg}")
            console.print('[dim]Enter JSON object (e.g., {"key": "value"})[/dim]')
            value_str = Prompt.ask("Value", default=default_str, console=console)
            value = _parse_value(value_str, "object")

        elif field_type == "number":
            default_str = str(current_value) if current_value is not None else ""
            value_str = Prompt.ask(prompt_msg, default=default_str, console=console)
            value = _parse_value(value_str, "number")

        else:
            # String or unknown type
            default_str = str(current_value) if current_value is not None else ""
            value = Prompt.ask(prompt_msg, default=default_str, console=console)

        resolved[name] = value

    console.print()
    return resolved


def _check_missing_required_inputs(input_schema: dict, provided_params: dict) -> list:
    """
    Check for missing required inputs that have no defaults.

    Args:
        input_schema: Dict of input name -> field definition
        provided_params: Provided parameter values

    Returns:
        List of missing required input names
    """
    missing = []
    for name, field in input_schema.items():
        if not isinstance(field, dict):
            continue
        if field.get("required", False):
            if name not in provided_params and field.get("default") is None:
                missing.append(name)
    return missing


@app.command()
def run(
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tac)"),
    storage: str = typer.Option("memory", help="Storage backend: memory, file"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
    openai_api_key: Optional[str] = typer.Option(
        None, envvar="OPENAI_API_KEY", help="OpenAI API key"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    log_level: Optional[str] = typer.Option(
        None, "--log-level", help="Log level: debug, info, warning, error, critical"
    ),
    log_format: str = typer.Option(
        "rich", "--log-format", help="Log format: rich (default), terminal, raw"
    ),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactively prompt for all inputs"
    ),
    mock_all: bool = typer.Option(
        False, "--mock-all", help="Mock all tools (use mock responses for all tool calls)"
    ),
    real_all: bool = typer.Option(
        False, "--real-all", help="Use real implementations for all tools (disable all mocks)"
    ),
    mock: Optional[list[str]] = typer.Option(None, "--mock", help="Mock specific tool(s) by name"),
    real: Optional[list[str]] = typer.Option(
        None, "--real", help="Use real implementation for specific tool(s)"
    ),
    sandbox: Optional[bool] = typer.Option(
        None,
        "--sandbox/--no-sandbox",
        help="Run in Docker sandbox (default: required unless --no-sandbox). "
        "Use --no-sandbox to run without isolation (security risk).",
    ),
    sandbox_broker: str = typer.Option(
        "tcp",
        "--sandbox-broker",
        help="Broker transport for sandbox runtime: tcp (default), tls, or stdio (deprecated due to buffering issues).",
    ),
    sandbox_network: Optional[str] = typer.Option(
        None,
        "--sandbox-network",
        help="Docker network mode for sandbox container (default: none for stdio; bridge for tcp/tls).",
    ),
    sandbox_broker_host: Optional[str] = typer.Option(
        None,
        "--sandbox-broker-host",
        help="Broker hostname from inside the sandbox container (tcp/tls only).",
    ),
):
    """
    Run a Tactus workflow.

    Examples:

        # Run with memory storage
        tactus run workflow.tac

        # Run with file storage
        tactus run workflow.tac --storage file --storage-path ./data

        # Pass parameters
        tactus run workflow.tac --param task="Analyze data" --param count=5

        # Interactive mode - prompt for all inputs
        tactus run workflow.tac -i

        # Mock all tools (useful for testing without real API calls)
        tactus run workflow.tac --mock-all

        # Mock specific tools
        tactus run workflow.tac --mock search --mock api_call

        # Use real implementation for specific tools while mocking others
        tactus run workflow.tac --mock-all --real done
    """
    setup_logging(verbose=verbose, log_level=log_level, log_format=log_format)

    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Determine format based on extension
    file_format = "lua" if workflow_file.suffix in [".tac", ".lua"] else "yaml"

    # Read workflow file
    source_content = workflow_file.read_text()

    # For Lua DSL files, extract input schema first
    input_schema = {}
    if file_format == "lua":
        try:
            validator = TactusValidator()
            validation_result = validator.validate(source_content, ValidationMode.QUICK)
            if validation_result.registry:
                input_schema = validation_result.registry.input_schema or {}
        except Exception as e:
            # If validation fails, we'll continue without input schema
            if verbose:
                console.print(f"[dim]Warning: Could not extract input schema: {e}[/dim]")

    # Parse parameters from CLI with type information from schema
    context = {}
    if param:
        for p in param:
            if "=" not in p:
                console.print(
                    f"[red]Error:[/red] Invalid parameter format: {p} (expected key=value)"
                )
                raise typer.Exit(1)
            key, value = p.split("=", 1)

            # Use type information from schema if available
            if input_schema and key in input_schema:
                field_def = input_schema[key]
                if isinstance(field_def, dict):
                    field_type = field_def.get("type", "string")
                    context[key] = _parse_value(value, field_type)
                    if verbose:
                        console.print(
                            f"[dim]Parsed {key} as {field_type}: {context[key]} (type: {type(context[key]).__name__})[/dim]"
                        )
                else:
                    # Fallback to JSON parsing
                    try:
                        context[key] = json.loads(value)
                    except json.JSONDecodeError:
                        context[key] = value
            else:
                # No schema info, try to parse JSON values
                try:
                    context[key] = json.loads(value)
                    if verbose:
                        console.print(
                            f"[dim]JSON parsed {key}: {context[key]} (type: {type(context[key]).__name__})[/dim]"
                        )
                except json.JSONDecodeError:
                    context[key] = value
                    if verbose:
                        console.print(f"[dim]String parsed {key}: {context[key]}[/dim]")

    # Handle interactive mode or missing required inputs
    if input_schema:
        missing_required = _check_missing_required_inputs(input_schema, context)

        if interactive:
            # Interactive mode: prompt for all inputs
            context = _prompt_for_inputs(console, input_schema, context)
        elif missing_required:
            # Missing required inputs - prompt for them
            console.print(
                f"[yellow]Missing required inputs: {', '.join(missing_required)}[/yellow]\n"
            )
            context = _prompt_for_inputs(console, input_schema, context)

    # Setup storage backend
    if storage == "memory":
        storage_backend = MemoryStorage()
    elif storage == "file":
        if not storage_path:
            storage_path = Path.cwd() / ".tac" / "storage"
        else:
            # Ensure storage_path is a directory path, not a file path
            storage_path = Path(storage_path)
            if storage_path.is_file():
                storage_path = storage_path.parent
        storage_backend = FileStorage(storage_dir=str(storage_path))
    else:
        console.print(f"[red]Error:[/red] Unknown storage backend: {storage}")
        raise typer.Exit(1)

    # HITL handler will be set up later after procedure_id is known
    hitl_handler = None

    # Load configuration cascade
    from tactus.core.config_manager import ConfigManager

    config_manager = ConfigManager()
    merged_config = config_manager.load_cascade(workflow_file)

    # CLI arguments override config values
    # Get OpenAI API key: CLI param > config > environment
    api_key = (
        openai_api_key or merged_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    )

    # Get tool paths from merged config
    tool_paths = merged_config.get("tool_paths")

    # Get MCP servers from merged config
    mcp_servers = merged_config.get("mcp_servers", {})

    # Handle sandbox mode
    from tactus.sandbox import (
        is_docker_available,
        SandboxConfig,
        ContainerRunner,
    )

    # Build sandbox config from merged config and CLI flag
    sandbox_config_dict = merged_config.get("sandbox", {})
    if sandbox is not None:
        # CLI flag overrides config
        sandbox_config_dict["enabled"] = sandbox
    else:
        # CLI default: require sandbox unless explicitly disabled
        if sandbox_config_dict.get("enabled") is None:
            sandbox_config_dict["enabled"] = True
    if sandbox_network is not None:
        sandbox_config_dict["network"] = sandbox_network
    if sandbox_broker_host is not None:
        sandbox_config_dict["broker_host"] = sandbox_broker_host

    sandbox_config_dict["broker_transport"] = sandbox_broker
    if (
        sandbox_network is None
        and sandbox_broker in ("tcp", "tls")
        and "network" not in sandbox_config_dict
    ):
        # Remote-mode requires container networking; default to bridge if user didn't specify.
        sandbox_config_dict["network"] = "bridge"
    sandbox_config = SandboxConfig(**sandbox_config_dict)

    # Pass logging preferences through to the sandbox container so container stderr matches CLI UX.
    sandbox_config.env.setdefault(
        "TACTUS_LOG_LEVEL", str(log_level or ("debug" if verbose else "info"))
    )
    sandbox_config.env.setdefault("TACTUS_LOG_FORMAT", str(log_format))

    # Check Docker availability
    docker_available, docker_reason = is_docker_available()

    # Determine if we should use sandbox
    use_sandbox = sandbox_config.should_use_sandbox(docker_available)

    if not use_sandbox:
        if sandbox_config.is_explicitly_disabled():
            # User explicitly disabled sandbox - show notice
            console.print(
                "[yellow][SANDBOX] Container isolation disabled (--no-sandbox or config).[/yellow]"
            )
            console.print("[yellow][SANDBOX] Proceeding without Docker isolation.[/yellow]")
        elif not docker_available and not sandbox_config.should_error_if_unavailable():
            # Sandbox is auto-mode (default): fall back when Docker is unavailable
            console.print(
                f"[yellow][SANDBOX] Docker not available ({docker_reason}); running without container isolation.[/yellow]"
            )
        elif sandbox_config.should_error_if_unavailable() and not docker_available:
            # Sandbox required but Docker unavailable - ERROR
            console.print(f"[red][SANDBOX ERROR] Docker not available: {docker_reason}[/red]")
            console.print(
                "[red][SANDBOX ERROR] Cannot run procedure without container isolation.[/red]"
            )
            console.print("[red][SANDBOX ERROR] Either:[/red]")
            console.print("[red]  - Start Docker Desktop / Docker daemon[/red]")
            console.print(
                "[red]  - Use --no-sandbox flag to explicitly run without isolation (security risk)[/red]"
            )
            console.print(
                "[red]  - Set sandbox.enabled: false in config to permanently disable (security risk)[/red]"
            )
            raise typer.Exit(1)

    # Note: CLI params have already been parsed and added to context above
    # This section used to re-parse them, but that would override the
    # properly JSON-parsed values with raw strings

    # Create log handler for Rich formatting
    from tactus.adapters.cli_log import CLILogHandler

    log_handler = CLILogHandler(console)

    # Suppress verbose runtime logging when using structured log handler
    # This prevents duplicate output - we only want the clean structured logs
    logging.getLogger("tactus.core.runtime").setLevel(logging.WARNING)
    logging.getLogger("tactus.primitives").setLevel(logging.WARNING)

    # Create runtime
    procedure_id = f"cli-{workflow_file.stem}"

    # Setup HITL handler - use new ControlLoopHandler with default channels
    from tactus.adapters.channels import load_default_channels
    from tactus.adapters.channels.cli import CLIControlChannel
    from tactus.adapters.control_loop import ControlLoopHandler, ControlLoopHITLAdapter

    # Load default channels (CLI if tty, IPC always)
    # Then add CLI with custom console if not already present
    channels = load_default_channels(procedure_id=procedure_id)

    # If CLI channel not already loaded (because not tty), add it with custom console
    if not any(c.channel_id == "cli" for c in channels):
        channels.insert(0, CLIControlChannel(console=console))

    control_handler = ControlLoopHandler(channels=channels, storage=storage_backend)
    hitl_handler = ControlLoopHITLAdapter(control_handler)

    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=storage_backend,
        hitl_handler=hitl_handler,
        chat_recorder=None,  # No chat recording in CLI mode
        mcp_server=None,  # Legacy parameter (deprecated)
        mcp_servers=mcp_servers,  # New multi-server support
        openai_api_key=api_key,
        log_handler=log_handler,
        tool_paths=tool_paths,
        source_file_path=str(workflow_file),
    )

    # Set up mocking based on CLI flags
    if mock_all or real_all or mock or real:
        from tactus.core.mocking import MockManager

        # Create and configure mock manager
        mock_manager = MockManager()
        runtime.mock_manager = mock_manager

        # Handle global flags
        if mock_all:
            mock_manager.enable_mock()
            runtime.mock_all_agents = True
            console.print("[yellow]Mocking enabled for all tools[/yellow]")
        elif real_all:
            mock_manager.disable_mock()
            console.print("[blue]Using real implementations for all tools[/blue]")

        # Handle specific tool mocking
        if mock:
            for tool_name in mock:
                # Register a simple mock that returns a placeholder response
                from tactus.core.mocking import MockConfig

                mock_manager.register_mock(
                    tool_name,
                    MockConfig(
                        tool_name=tool_name,
                        static_result={
                            "mocked": True,
                            "tool": tool_name,
                            "message": f"Mock response for {tool_name}",
                        },
                    ),
                )
                mock_manager.enable_mock(tool_name)
                console.print(f"[yellow]Mocking enabled for tool: {tool_name}[/yellow]")

        # Handle specific tool real implementations
        if real:
            for tool_name in real:
                mock_manager.disable_mock(tool_name)
                console.print(f"[blue]Using real implementation for tool: {tool_name}[/blue]")

    # Execute procedure
    if use_sandbox:
        console.print(
            f"[blue]Running procedure in sandbox:[/blue] [bold]{workflow_file.name}[/bold] ({file_format} format)\n"
        )
    else:
        console.print(
            f"[blue]Running procedure:[/blue] [bold]{workflow_file.name}[/bold] ({file_format} format)\n"
        )

    try:
        if use_sandbox:
            # Host-side broker reads OpenAI credentials from the host process environment.
            # Keep secrets OUT of the sandbox container by setting the env var only on the host.
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key

            # Execute in Docker sandbox
            runner = ContainerRunner(sandbox_config)
            sandbox_result = asyncio.run(
                runner.run(
                    source=source_content,
                    params=context,
                    source_file_path=str(workflow_file),
                    format=file_format,
                )
            )

            # Convert sandbox result to the expected format
            if sandbox_result.status.value == "success":
                result = {
                    "success": True,
                    "result": sandbox_result.result,
                    "state": sandbox_result.metadata.get("state", {}),
                    "iterations": sandbox_result.metadata.get("iterations", 0),
                    "tools_used": sandbox_result.metadata.get("tools_used", []),
                }
            else:
                result = {
                    "success": False,
                    "error": sandbox_result.error,
                }
                if sandbox_result.traceback and verbose:
                    console.print(f"[dim]{sandbox_result.traceback}[/dim]")
        else:
            # Execute directly (non-sandboxed)
            try:
                result = asyncio.run(runtime.execute(source_content, context, format=file_format))
            except Exception as e:
                from tactus.core.exceptions import ProcedureWaitingForHuman

                # Check both the exception itself and its __cause__
                console.print(f"[dim]DEBUG: Caught exception type: {type(e).__name__}[/dim]")
                console.print(
                    f"[dim]DEBUG: Exception __cause__ type: {type(e.__cause__).__name__ if e.__cause__ else 'None'}[/dim]"
                )
                console.print(
                    f"[dim]DEBUG: Is ProcedureWaitingForHuman: {isinstance(e, ProcedureWaitingForHuman)}[/dim]"
                )
                console.print(
                    f"[dim]DEBUG: __cause__ is ProcedureWaitingForHuman: {isinstance(e.__cause__, ProcedureWaitingForHuman) if e.__cause__ else False}[/dim]"
                )

                if isinstance(e, ProcedureWaitingForHuman):
                    # Direct exception
                    console.print(
                        "\n[yellow]⏸ Procedure paused - waiting for human response[/yellow]"
                    )
                    console.print(f"[dim]Message ID: {e.pending_message_id}[/dim]")
                    console.print("\n[cyan]The procedure has been paused and is waiting for input.")
                    console.print(
                        "To resume, run the procedure again or provide a response via another channel.[/cyan]\n"
                    )
                    return
                elif e.__cause__ and isinstance(e.__cause__, ProcedureWaitingForHuman):
                    # Wrapped exception
                    console.print(
                        "\n[yellow]⏸ Procedure paused - waiting for human response[/yellow]"
                    )
                    console.print(f"[dim]Message ID: {e.__cause__.pending_message_id}[/dim]")
                    console.print("\n[cyan]The procedure has been paused and is waiting for input.")
                    console.print(
                        "To resume, run the procedure again or provide a response via another channel.[/cyan]\n"
                    )
                    return
                else:
                    # Re-raise other exceptions
                    raise

        if result["success"]:
            console.print("\n[green]✓ Procedure completed successfully[/green]\n")

            # Display results
            if result.get("result"):
                console.print("\n[green]Result:[/green]")
                display_result = result["result"]
                try:
                    from tactus.protocols.result import TactusResult

                    if isinstance(display_result, TactusResult):
                        display_result = display_result.output
                except Exception:
                    pass

                console.print(f"  {display_result}")

            # Display state
            if result.get("state"):
                state_table = Table(title="Final State")
                state_table.add_column("Key", style="cyan")
                state_table.add_column("Value", style="magenta")

                for key, value in result["state"].items():
                    state_table.add_row(key, str(value))

                console.print(state_table)

            # Display stats
            console.print(f"\n[dim]Iterations: {result.get('iterations', 0)}[/dim]")
            console.print(
                f"[dim]Tools used: {', '.join(result.get('tools_used', [])) or 'None'}[/dim]"
            )

        else:
            console.print("\n[red]✗ Workflow failed[/red]\n")
            if result.get("error"):
                console.print(f"[red]Error: {result['error']}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Execution error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


# Sandbox subcommand group
sandbox_app = typer.Typer(help="Manage Docker sandbox for secure procedure execution")
app.add_typer(sandbox_app, name="sandbox")


@sandbox_app.command("status")
def sandbox_status():
    """
    Show Docker sandbox status and availability.

    Displays whether Docker is available and if the sandbox image exists.
    """
    from tactus.sandbox import is_docker_available, DockerManager

    # Check Docker availability
    available, reason = is_docker_available()

    console.print("\n[bold]Docker Sandbox Status[/bold]\n")

    if available:
        console.print("[green]Docker:[/green] Available")
    else:
        console.print(f"[red]Docker:[/red] Not available - {reason}")

    # Check image status
    manager = DockerManager()
    if manager.image_exists():
        version = manager.get_image_version() or "unknown"
        console.print(
            f"[green]Sandbox image:[/green] {manager.full_image_name} (version: {version})"
        )
    else:
        console.print(f"[yellow]Sandbox image:[/yellow] Not built ({manager.full_image_name})")
        console.print("[dim]Run 'tactus sandbox rebuild' to build the image[/dim]")

    console.print()


@sandbox_app.command("rebuild")
def sandbox_rebuild(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show build output"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild even if image exists"),
):
    """
    Build or rebuild the Docker sandbox image.

    Creates the sandbox image used for isolated procedure execution.
    """
    from pathlib import Path
    from tactus.sandbox import is_docker_available, DockerManager
    from tactus.sandbox.docker_manager import resolve_dockerfile_path
    import tactus

    # Check Docker availability
    available, reason = is_docker_available()
    if not available:
        console.print(f"[red]Error:[/red] Docker not available - {reason}")
        raise typer.Exit(1)

    # Get Tactus package path for build context
    tactus_path = Path(tactus.__file__).parent.parent
    dockerfile_path, build_mode = resolve_dockerfile_path(tactus_path)

    if not dockerfile_path.exists():
        console.print(f"[red]Error:[/red] Dockerfile not found: {dockerfile_path}")
        console.print("[dim]This may indicate an incomplete installation.[/dim]")
        raise typer.Exit(1)

    # Get version
    version = getattr(tactus, "__version__", "dev")

    manager = DockerManager()

    if not force and manager.image_exists():
        image_version = manager.get_image_version()
        if image_version == version:
            console.print(
                f"[green]Image is up to date:[/green] {manager.full_image_name} (v{version})"
            )
            console.print("[dim]Use --force to rebuild anyway[/dim]")
            return

    console.print(f"[blue]Building sandbox image:[/blue] {manager.full_image_name}")
    console.print(f"[dim]Version: {version}[/dim]")
    console.print(f"[dim]Context: {tactus_path}[/dim]\n")
    if build_mode == "pypi":
        console.print(
            "[yellow]No source tree detected; building image by installing tactus from PyPI.[/yellow]"
        )

    success, message = manager.build_image(
        dockerfile_path=dockerfile_path,
        context_path=tactus_path,
        version=version,
        verbose=verbose,
    )

    if success:
        console.print("\n[green]Successfully built sandbox image[/green]")
    else:
        console.print(f"\n[red]Failed to build sandbox image:[/red] {message}")
        raise typer.Exit(1)


@app.command()
def validate(
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tac or .lua)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quick: bool = typer.Option(False, "--quick", help="Quick validation (syntax only)"),
):
    """
    Validate a Tactus workflow file.

    Examples:

        tactus validate workflow.tac
        tactus validate workflow.lua --quick
    """
    setup_logging(verbose)

    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Determine format based on extension
    file_format = "lua" if workflow_file.suffix in [".tac", ".lua"] else "yaml"

    # Read workflow file
    source_content = workflow_file.read_text()

    console.print(f"Validating: [bold]{workflow_file.name}[/bold] ({file_format} format)")

    try:
        if file_format == "lua":
            # Use new validator for Lua DSL
            validator = TactusValidator()
            mode = ValidationMode.QUICK if quick else ValidationMode.FULL
            result = validator.validate(source_content, mode)

            if result.valid:
                console.print("\n[green]✓ DSL is valid[/green]\n")

                # Display warnings
                if result.warnings:
                    for warning in result.warnings:
                        console.print(f"[yellow]⚠ Warning:[/yellow] {warning.message}")
                    console.print()

                if result.registry:
                    # Convert registry to config dict for display
                    config = {
                        "description": result.registry.description,
                        "agents": {},
                        "output": {},
                        "params": {},
                    }
                    # Convert Pydantic models to dicts
                    for name, agent in result.registry.agents.items():
                        config["agents"][name] = {
                            "system_prompt": agent.system_prompt,
                            "provider": agent.provider,
                            "model": agent.model,
                        }
                    for name, output in result.registry.output_schema.items():
                        if output is not None:
                            config["output"][name] = {
                                "type": (
                                    output.get("type", "string")
                                    if isinstance(output, dict)
                                    else "string"
                                ),
                                "required": (
                                    output.get("required", False)
                                    if isinstance(output, dict)
                                    else False
                                ),
                            }
                    for name, param in result.registry.input_schema.items():
                        if param is not None:
                            config["params"][name] = {
                                "type": (
                                    param.get("type", "string")
                                    if isinstance(param, dict)
                                    else "string"
                                ),
                                "required": (
                                    param.get("required", False)
                                    if isinstance(param, dict)
                                    else False
                                ),
                                "default": (
                                    param.get("default") if isinstance(param, dict) else None
                                ),
                            }
                else:
                    config = {}
            else:
                console.print("\n[red]✗ DSL validation failed[/red]\n")
                for error in result.errors:
                    console.print(f"[red]  • {error.message}[/red]")
                raise typer.Exit(1)
        else:
            # Parse YAML (legacy)
            config = ProcedureYAMLParser.parse(source_content)

        # Display validation results
        console.print("\n[green]✓ YAML is valid[/green]\n")

        # Show config details
        info_table = Table(title="Workflow Info")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="magenta")

        info_table.add_row("Name", config.get("name", "N/A"))
        info_table.add_row("Version", config.get("version", "N/A"))
        info_table.add_row("Class", config.get("class", "LuaDSL"))

        if config.get("description"):
            info_table.add_row("Description", config["description"])

        console.print(info_table)

        # Show agents
        if config.get("agents"):
            agents_table = Table(title="Agents")
            agents_table.add_column("Name", style="cyan")
            agents_table.add_column("System Prompt", style="magenta")

            for name, agent_config in config["agents"].items():
                prompt = agent_config.get("system_prompt", "N/A")
                # Truncate long prompts
                if len(prompt) > 50:
                    prompt = prompt[:47] + "..."
                agents_table.add_row(name, prompt)

            console.print(agents_table)

        # Show outputs
        if config.get("output"):
            outputs_table = Table(title="Outputs")
            outputs_table.add_column("Name", style="cyan")
            outputs_table.add_column("Type", style="magenta")
            outputs_table.add_column("Required", style="yellow")

            for name, output_config in config["output"].items():
                outputs_table.add_row(
                    name,
                    output_config.get("type", "any"),
                    "✓" if output_config.get("required", False) else "",
                )

            console.print(outputs_table)

        # Show parameters
        if config.get("params"):
            params_table = Table(title="Parameters")
            params_table.add_column("Name", style="cyan")
            params_table.add_column("Type", style="magenta")
            params_table.add_column("Default", style="yellow")

            for name, param_config in config["params"].items():
                params_table.add_row(
                    name, param_config.get("type", "any"), str(param_config.get("default", ""))
                )

            console.print(params_table)

        console.print("\n[green]Validation complete![/green]")

    except ProcedureConfigError as e:
        console.print("\n[red]✗ Validation failed:[/red]\n")
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    except Exception as e:
        console.print("\n[red]✗ Unexpected error:[/red]\n")
        console.print(f"[red]{e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command("format")
def format_(
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tac or .lua)"),
    check: bool = typer.Option(
        False,
        "--check",
        help="Don't write files back; exit 1 if changes are needed",
    ),
    stdout: bool = typer.Option(False, "--stdout", help="Write formatted code to stdout"),
):
    """
    Format a Tactus Lua DSL file.

    Currently enforces semantic indentation using 2-space soft tabs.
    """
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    if workflow_file.suffix not in [".tac", ".lua"]:
        console.print("[red]Error:[/red] Formatting is only supported for .tac/.lua files")
        raise typer.Exit(1)

    formatter = TactusFormatter(indent_width=2)
    source_content = workflow_file.read_text()

    try:
        result = formatter.format_source(source_content)
    except FormattingError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)

    if stdout:
        sys.stdout.write(result.formatted)
        return

    if check:
        if result.changed:
            console.print(f"[red]✗ Would reformat:[/red] {workflow_file}")
            raise typer.Exit(1)
        console.print(f"[green]✓ Already formatted:[/green] {workflow_file}")
        return

    if result.changed:
        workflow_file.write_text(result.formatted)
        console.print(f"[green]✓ Formatted:[/green] {workflow_file}")
    else:
        console.print(f"[green]✓ No changes:[/green] {workflow_file}")


@app.command()
def info(
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tac or .lua)"),
):
    """
    Display procedure metadata (agents, tools, parameters, outputs).

    Examples:

        tactus info workflow.tac
    """
    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Determine format based on extension
    file_format = "lua" if workflow_file.suffix in [".tac", ".lua"] else "yaml"

    # Read workflow file
    source_content = workflow_file.read_text()

    console.print(f"[blue]Procedure info:[/blue] [bold]{workflow_file.name}[/bold]\n")

    try:
        if file_format == "lua":
            # Use validator to parse procedure
            validator = TactusValidator()
            result = validator.validate(source_content, ValidationMode.FULL)

            if not result.valid:
                console.print("[red]✗ Invalid procedure - cannot display info[/red]\n")
                for error in result.errors:
                    console.print(f"  [red]•[/red] {error.message}")
                raise typer.Exit(1)

            registry = result.registry

            # Display procedure name
            if registry.description:
                console.print(f"[cyan]Description:[/cyan] {registry.description}\n")

            # Show parameters (input)
            if registry.input_schema:
                console.print("[cyan]Parameters:[/cyan]")
                for name, field_config in registry.input_schema.items():
                    if field_config is None:
                        # Handle None field_config
                        console.print(f"  [bold]{name}[/bold]: any")
                    elif isinstance(field_config, dict):
                        field_type = field_config.get("type", "any")
                        required = field_config.get("required", False)
                        default = field_config.get("default")
                        req_str = "[yellow](required)[/yellow]" if required else ""
                        default_str = (
                            f" [dim]default: {default}[/dim]" if default is not None else ""
                        )
                        console.print(f"  [bold]{name}[/bold]: {field_type} {req_str}{default_str}")
                    else:
                        # Handle other types
                        console.print(f"  [bold]{name}[/bold]: {type(field_config).__name__}")
                console.print()

            # Show outputs
            if registry.output_schema:
                console.print("[cyan]Outputs:[/cyan]")
                for name, field_config in registry.output_schema.items():
                    if field_config is None:
                        # Handle None field_config
                        console.print(f"  [bold]{name}[/bold]: any")
                    elif isinstance(field_config, dict):
                        field_type = field_config.get("type", "any")
                        required = field_config.get("required", False)
                        description = field_config.get("description", "")
                        req_str = "[yellow](required)[/yellow]" if required else ""
                        desc_str = f" [dim]- {description}[/dim]" if description else ""
                        console.print(f"  [bold]{name}[/bold]: {field_type} {req_str}{desc_str}")
                    else:
                        # Handle other types (shouldn't happen, but be safe)
                        console.print(f"  [bold]{name}[/bold]: {type(field_config).__name__}")
                console.print()

            # Show agents
            if registry.agents:
                console.print("[cyan]Agents:[/cyan]")
                for name, agent_def in registry.agents.items():
                    console.print(f"  [bold]{name}[/bold]:")
                    console.print(f"    Provider: {agent_def.provider}")
                    if agent_def.model:
                        if isinstance(agent_def.model, str):
                            model_str = agent_def.model
                        elif isinstance(agent_def.model, dict):
                            model_str = agent_def.model.get("name", "default")
                        else:
                            model_str = str(agent_def.model)
                        console.print(f"    Model: {model_str}")
                    if agent_def.tools:
                        tools_str = ", ".join(agent_def.tools)
                        console.print(f"    Tools: {tools_str}")
                    if agent_def.system_prompt:
                        # Show first 100 chars of system prompt
                        prompt_preview = (
                            agent_def.system_prompt[:100] + "..."
                            if len(agent_def.system_prompt) > 100
                            else agent_def.system_prompt
                        )
                        console.print(f"    Prompt: [dim]{prompt_preview}[/dim]")
                    console.print()

            # Show specifications
            if registry.specifications:
                console.print(
                    f"[cyan]Specifications:[/cyan] {len(registry.specifications)} scenario(s)"
                )

        else:
            console.print("[red]Only .tac/.lua files are supported for info command[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Error displaying info:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def test(
    procedure_file: Path = typer.Argument(..., help="Path to procedure file (.tac or .lua)"),
    runs: int = typer.Option(1, help="Number of runs per scenario (for consistency check)"),
    scenario: Optional[str] = typer.Option(None, help="Run specific scenario"),
    parallel: bool = typer.Option(True, help="Run scenarios in parallel"),
    workers: Optional[int] = typer.Option(None, help="Number of parallel workers"),
    mock: bool = typer.Option(False, help="Use mocked tools (fast, deterministic)"),
    mock_config: Optional[Path] = typer.Option(None, help="Path to mock config JSON"),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Run BDD specifications for a procedure.

    Can run scenarios once (standard test) or multiple times (consistency evaluation).

    Examples:

        # Run all scenarios once
        tactus test procedure.tac

        # Check consistency (run 10 times per scenario)
        tactus test procedure.tac --runs 10

        # Run with mocked tools
        tactus test procedure.tac --mock

        # Run specific scenario
        tactus test procedure.tac --scenario "Agent completes research"
    """
    setup_logging(verbose)

    if not procedure_file.exists():
        console.print(f"[red]Error:[/red] File not found: {procedure_file}")
        raise typer.Exit(1)

    mode_str = "mocked" if (mock or mock_config) else "real"
    if runs > 1:
        console.print(
            Panel(f"Running Consistency Check ({runs} runs, {mode_str} mode)", style="blue")
        )
    else:
        console.print(Panel(f"Running BDD Tests ({mode_str} mode)", style="blue"))

    try:
        from tactus.testing.test_runner import TactusTestRunner
        from tactus.testing.evaluation_runner import TactusEvaluationRunner
        from tactus.testing.mock_tools import create_default_mocks
        from tactus.validation import TactusValidator
        from tactus.core.config_manager import ConfigManager
        import json

        # Load configuration and export all values as environment variables
        config_mgr = ConfigManager()
        config = config_mgr.load_cascade(procedure_file)

        # Export config values as environment variables (matching ConfigManager's env_mappings)
        env_mappings = {
            "openai_api_key": "OPENAI_API_KEY",
            "google_api_key": "GOOGLE_API_KEY",
            ("aws", "access_key_id"): "AWS_ACCESS_KEY_ID",
            ("aws", "secret_access_key"): "AWS_SECRET_ACCESS_KEY",
            ("aws", "default_region"): "AWS_DEFAULT_REGION",
            ("aws", "profile"): "AWS_PROFILE",
        }

        for config_key, env_key in env_mappings.items():
            # Skip if environment variable is already set
            if env_key in os.environ:
                continue

            # Get value from config
            if isinstance(config_key, tuple):
                # Nested key (e.g., aws.access_key_id)
                value = config.get(config_key[0], {}).get(config_key[1])
            else:
                value = config.get(config_key)

            # Set environment variable if value exists
            if value:
                os.environ[env_key] = str(value)

        # Validate and extract specifications
        validator = TactusValidator()
        result = validator.validate_file(str(procedure_file))

        if not result.valid:
            console.print("[red]✗ Validation failed:[/red]")
            for error in result.errors:
                console.print(f"  [red]• {error.message}[/red]")
            raise typer.Exit(1)

        # Check if specifications exist
        if not result.registry or not result.registry.gherkin_specifications:
            console.print("[yellow]⚠ No specifications found in procedure file[/yellow]")
            console.print("Add specifications using: specifications([[ ... ]])")
            raise typer.Exit(1)

        # Load mock config if provided
        mock_tools = {}
        if mock or mock_config:
            if mock_config:
                mock_tools = json.loads(mock_config.read_text())
                console.print(f"[cyan]Loaded mock config: {mock_config}[/cyan]")
            else:
                mock_tools = create_default_mocks()
                console.print("[cyan]Using default mocks[/cyan]")

        # Parse parameters
        test_params = {}
        if param:
            for p in param:
                if "=" in p:
                    key, value = p.split("=", 1)
                    test_params[key] = value

        if runs > 1:
            # Run consistency evaluation
            evaluator = TactusEvaluationRunner(
                procedure_file, mock_tools=mock_tools, params=test_params
            )
            evaluator.setup(
                result.registry.gherkin_specifications,
                custom_steps_dict=result.registry.custom_steps,
            )

            if scenario:
                eval_results = [evaluator.evaluate_scenario(scenario, runs, parallel)]
            else:
                eval_results = evaluator.evaluate_all(runs, parallel)

            _display_evaluation_results(eval_results)
            evaluator.cleanup()

        else:
            # Run standard test
            runner = TactusTestRunner(procedure_file, mock_tools=mock_tools, params=test_params)
            runner.setup(
                result.registry.gherkin_specifications,
                custom_steps_dict=result.registry.custom_steps,
            )

            test_result = runner.run_tests(parallel=parallel, scenario_filter=scenario)

            _display_test_results(test_result)
            runner.cleanup()

            if test_result.failed_scenarios > 0:
                raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _display_test_results(test_result):
    """Display test results in Rich format."""

    for feature in test_result.features:
        console.print(f"\n[bold]Feature:[/bold] {feature.name}")

        for scenario in feature.scenarios:
            status_icon = "✓" if scenario.status == "passed" else "✗"
            status_color = "green" if scenario.status == "passed" else "red"

            # Include execution metrics in scenario display
            metrics_parts = []
            if scenario.total_cost > 0:
                metrics_parts.append(f"💰 ${scenario.total_cost:.6f}")
            if scenario.llm_calls > 0:
                metrics_parts.append(f"🤖 {scenario.llm_calls} LLM calls")
            if scenario.iterations > 0:
                metrics_parts.append(f"🔄 {scenario.iterations} iterations")
            if scenario.tools_used:
                metrics_parts.append(f"🔧 {len(scenario.tools_used)} tools")

            metrics_str = f" ({', '.join(metrics_parts)})" if metrics_parts else ""
            console.print(
                f"  [{status_color}]{status_icon}[/{status_color}] "
                f"Scenario: {scenario.name} ({scenario.duration:.2f}s){metrics_str}"
            )

            if scenario.status == "failed":
                for step in scenario.steps:
                    if step.status == "failed":
                        console.print(f"    [red]Failed:[/red] {step.keyword} {step.message}")
                        if step.error_message:
                            console.print(f"      {step.error_message}")

    # Summary
    console.print(
        f"\n{test_result.total_scenarios} scenarios "
        f"([green]{test_result.passed_scenarios} passed[/green], "
        f"[red]{test_result.failed_scenarios} failed[/red])"
    )

    # Execution metrics summary
    if test_result.total_cost > 0 or test_result.total_llm_calls > 0:
        console.print("\n[bold]Execution Metrics:[/bold]")
        if test_result.total_cost > 0:
            console.print(
                f"  💰 Cost: ${test_result.total_cost:.6f} ({test_result.total_tokens:,} tokens)"
            )
        if test_result.total_llm_calls > 0:
            console.print(f"  🤖 LLM Calls: {test_result.total_llm_calls}")
        if test_result.total_iterations > 0:
            console.print(f"  🔄 Iterations: {test_result.total_iterations}")
        if test_result.unique_tools_used:
            console.print(f"  🔧 Tools: {', '.join(test_result.unique_tools_used)}")


def _display_evaluation_results(eval_results):
    """Display evaluation results with metrics."""

    for eval_result in eval_results:
        console.print(f"\n[bold]Scenario:[/bold] {eval_result.scenario_name}")

        # Success rate
        rate_color = "green" if eval_result.success_rate >= 0.9 else "yellow"
        console.print(
            f"  Success Rate: [{rate_color}]{eval_result.success_rate:.1%}[/{rate_color}] "
            f"({eval_result.passed_runs}/{eval_result.total_runs})"
        )

        # Timing
        console.print(
            f"  Duration: {eval_result.mean_duration:.2f}s (±{eval_result.stddev_duration:.2f}s)"
        )

        # Consistency
        consistency_color = "green" if eval_result.consistency_score >= 0.9 else "yellow"
        console.print(
            f"  Consistency: [{consistency_color}]{eval_result.consistency_score:.1%}[/{consistency_color}]"
        )

        # Flakiness warning
        if eval_result.is_flaky:
            console.print("  [yellow]⚠️  FLAKY - Inconsistent results detected[/yellow]")


def _display_eval_results(report, runs: int, console):
    """Display evaluation results with per-task success rate breakdown."""
    from collections import defaultdict
    from rich.panel import Panel
    from rich import box

    # Group results by original case name
    case_results = defaultdict(list)
    for case in report.cases:
        # Extract original case name from the case name (e.g., "simple_greeting_run1" -> "simple_greeting")
        case_name = case.name
        if "_run" in case_name:
            original_name = case_name.rsplit("_run", 1)[0]
        else:
            original_name = case_name
        case_results[original_name].append(case)

    # Display per-task breakdown with details
    if runs > 1:
        console.print("\n[bold cyan]Evaluation Results by Task[/bold cyan]\n")

        for task_name, cases in sorted(case_results.items()):
            total_runs = len(cases)
            # A case is successful if ALL its assertions passed
            successful_runs = sum(1 for c in cases if all(a.value for a in c.assertions.values()))
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

            # Calculate per-evaluator pass rates
            evaluator_stats = defaultdict(lambda: {"passed": 0, "total": 0})
            for case in cases:
                for eval_name, assertion in case.assertions.items():
                    evaluator_stats[eval_name]["total"] += 1
                    if assertion.value:
                        evaluator_stats[eval_name]["passed"] += 1

            # Status styling
            status_icon = "✔" if success_rate >= 80 else "⚠" if success_rate >= 50 else "✗"
            rate_color = (
                "green" if success_rate >= 80 else "yellow" if success_rate >= 50 else "red"
            )

            # Create task summary
            summary = f"[bold]{task_name}[/bold]\n"
            summary += f"[{rate_color}]{status_icon} Success Rate: {success_rate:.1f}% ({successful_runs}/{total_runs} runs passed all evaluators)[/{rate_color}]\n"

            # Add evaluator breakdown
            summary += "\n[dim]Evaluator Breakdown:[/dim]\n"
            for eval_name, stats in evaluator_stats.items():
                eval_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
                eval_color = "green" if eval_rate >= 80 else "yellow" if eval_rate >= 50 else "red"
                summary += f"  [{eval_color}]{eval_name}: {eval_rate:.0f}% ({stats['passed']}/{stats['total']})[/{eval_color}]\n"

            # Show detailed sample runs
            summary += "\n[dim]Sample Runs (showing first 3):[/dim]"
            for i, case in enumerate(cases[:3], 1):  # Show first 3 runs
                all_passed = all(a.value for a in case.assertions.values())
                icon = "✔" if all_passed else "✗"
                summary += f"\n\n  {icon} [bold]Run {i}:[/bold]"

                # Show input
                summary += f"\n    [dim]Input:[/dim] {case.inputs}"

                # Show output (formatted nicely)
                summary += "\n    [dim]Output:[/dim]"
                if isinstance(case.output, dict):
                    for key, value in case.output.items():
                        value_str = str(value)
                        if len(value_str) > 200:
                            value_str = value_str[:197] + "..."
                        summary += f"\n      {key}: {value_str}"
                else:
                    output_str = str(case.output)
                    if len(output_str) > 200:
                        output_str = output_str[:197] + "..."
                    summary += f" {output_str}"

                # Show assertion results for this run
                summary += "\n    [dim]Evaluators:[/dim]"
                for eval_name, assertion in case.assertions.items():
                    result_icon = "✔" if assertion.value else "✗"
                    summary += f"\n      {result_icon} {eval_name}"
                    # Show reason if available (e.g., from LLM judge)
                    if hasattr(assertion, "reason") and assertion.reason:
                        reason_lines = assertion.reason.split("\n")
                        # Show first line inline, rest indented
                        if reason_lines:
                            summary += f": {reason_lines[0]}"
                            for line in reason_lines[1:3]:  # Show up to 2 more lines
                                if line.strip():
                                    summary += f"\n         {line.strip()}"
                            if len(reason_lines) > 3:
                                summary += "\n         [dim]...[/dim]"

            if len(cases) > 3:
                summary += f"\n\n  [dim]... and {len(cases) - 3} more runs (use --verbose to see all)[/dim]"

            console.print(Panel(summary, box=box.ROUNDED, border_style=rate_color))
            console.print()
    else:
        # Single run - just show the standard report
        console.print("\n[bold]Detailed Results:[/bold]")
        report.print(include_input=True, include_output=True)


@app.command()
def eval(
    procedure_file: Path = typer.Argument(..., help="Path to procedure file (.tac)"),
    runs: int = typer.Option(1, help="Number of runs per case"),
    parallel: bool = typer.Option(True, help="Run cases in parallel"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Run Pydantic Evals evaluation on procedure.

    Evaluates LLM agent quality, consistency, and performance using
    the Pydantic Evals framework. Requires evaluations() block in
    the procedure file.

    Examples:

        # Run evaluation once per case
        tactus eval procedure.tac

        # Run evaluation 10 times per case to measure consistency
        tactus eval procedure.tac --runs 10

        # Run sequentially (for debugging)
        tactus eval procedure.tac --no-parallel
    """
    setup_logging(verbose)
    load_tactus_config()

    if not procedure_file.exists():
        console.print(f"[red]Error:[/red] File not found: {procedure_file}")
        raise typer.Exit(1)

    try:
        from tactus.testing.pydantic_eval_runner import TactusPydanticEvalRunner
        from tactus.testing.eval_models import EvaluationConfig, EvalCase, EvaluatorConfig
        from tactus.validation import TactusValidator

        # Validate and extract evaluations config
        validator = TactusValidator()
        result = validator.validate_file(str(procedure_file))

        if not result.valid:
            console.print("[red]✗ Validation failed:[/red]")
            for error in result.errors:
                console.print(f"  [red]• {error.message}[/red]")
            raise typer.Exit(1)

        # Check if evaluations exist
        if not result.registry or not result.registry.pydantic_evaluations:
            console.print("[yellow]⚠ No evaluations found in procedure file[/yellow]")
            console.print(
                "Add evaluations using: evaluations({ dataset = {...}, evaluators = {...} })"
            )
            raise typer.Exit(1)

        # Convert registry evaluations to EvaluationConfig
        eval_dict = result.registry.pydantic_evaluations

        # Parse dataset
        dataset_cases = []
        for case_dict in eval_dict.get("dataset", []):
            dataset_cases.append(EvalCase(**case_dict))

        # Parse evaluators
        evaluators = []
        for eval_dict_item in eval_dict.get("evaluators", []):
            evaluators.append(EvaluatorConfig(**eval_dict_item))

        # Parse thresholds if present
        thresholds = None
        if "thresholds" in eval_dict:
            from tactus.testing.eval_models import EvaluationThresholds

            thresholds = EvaluationThresholds(**eval_dict["thresholds"])

        # Create evaluation config
        # Use runs from file if specified, otherwise use CLI parameter
        file_runs = eval_dict.get("runs", 1)
        actual_runs = (
            runs if runs != 1 else file_runs
        )  # CLI default is 1, so if it's 1, use file value

        console.print(
            Panel(f"Running Pydantic Evals Evaluation ({actual_runs} runs per case)", style="blue")
        )

        eval_config = EvaluationConfig(
            dataset=dataset_cases,
            evaluators=evaluators,
            runs=actual_runs,
            parallel=parallel,
            thresholds=thresholds,
        )

        # Get OpenAI API key
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            console.print("[yellow]⚠ Warning: OPENAI_API_KEY not set[/yellow]")

        # Run evaluation
        runner = TactusPydanticEvalRunner(
            procedure_file=procedure_file,
            eval_config=eval_config,
            openai_api_key=openai_api_key,
        )

        report = runner.run_evaluation()

        # Display results with custom formatting for success rates
        console.print("\n")
        _display_eval_results(report, actual_runs, console)

        # Check thresholds
        passed, violations = runner.check_thresholds(report)

        if not passed:
            console.print("\n[red]❌ Evaluation failed threshold checks:[/red]")
            for violation in violations:
                console.print(f"  • {violation}")
            raise typer.Exit(code=1)
        elif eval_config.thresholds:
            # Only show success message if thresholds were configured
            console.print("\n[green]✓ All thresholds met[/green]")

    except ImportError as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        console.print("\n[yellow]Install pydantic-evals:[/yellow]")
        console.print("  pip install pydantic-evals")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


def _display_pydantic_eval_results(report):
    """Display Pydantic Evals results in Rich format."""

    # Summary header
    console.print("\n[bold]Evaluation Results:[/bold]")

    # Overall stats
    total_cases = len(report.cases) if hasattr(report, "cases") else 0
    if total_cases == 0:
        console.print("[yellow]No cases found in report[/yellow]")
        return

    passed_cases = sum(
        1 for case in report.cases if all(assertion for assertion in case.assertions.values())
    )

    console.print(
        f"  Cases: {total_cases} total, "
        f"[green]{passed_cases} passed[/green], "
        f"[red]{total_cases - passed_cases} failed[/red]"
    )

    # Per-case results
    for case in report.cases:
        console.print(f"\n[bold cyan]Case:[/bold cyan] {case.name}")

        # Assertions (pass/fail evaluators)
        if case.assertions:
            console.print("  [bold]Assertions:[/bold]")
            for name, passed in case.assertions.items():
                icon = "✓" if passed else "✗"
                color = "green" if passed else "red"
                console.print(f"    [{color}]{icon}[/{color}] {name}")

        # Scores (numeric evaluators like LLM judge)
        if case.scores:
            console.print("  [bold]Scores:[/bold]")
            for name, score in case.scores.items():
                console.print(f"    {name}: {score:.2f}")

        # Labels (categorical evaluators)
        if case.labels:
            console.print("  [bold]Labels:[/bold]")
            for name, label in case.labels.items():
                console.print(f"    {name}: {label}")

        # Duration
        console.print(f"  Duration: {case.task_duration:.2f}s")

    # Averages
    if report.cases:
        console.print("\n[bold]Averages:[/bold]")

        # Average scores
        all_scores = {}
        for case in report.cases:
            for name, score in case.scores.items():
                if name not in all_scores:
                    all_scores[name] = []
                all_scores[name].append(score)

        for name, scores in all_scores.items():
            avg_score = sum(scores) / len(scores)
            console.print(f"  {name}: {avg_score:.2f}")

        # Average duration
        avg_duration = sum(case.task_duration for case in report.cases) / len(report.cases)
        console.print(f"  Duration: {avg_duration:.2f}s")


@app.command()
def version():
    """Show Tactus version."""
    from tactus import __version__

    console.print(f"Tactus version: [bold]{__version__}[/bold]")


@app.command()
def ide(
    port: Optional[int] = typer.Option(None, help="Backend port (auto-detected if not specified)"),
    frontend_port: int = typer.Option(3000, help="Frontend port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Start the Tactus IDE with integrated backend and frontend.

    The IDE provides a Monaco-based editor with syntax highlighting,
    validation, and LSP features for Tactus DSL files.

    Examples:

        # Start IDE (auto-detects available port)
        tactus ide

        # Start on specific port
        tactus ide --port 5001

        # Start without opening browser
        tactus ide --no-browser
    """
    import socket
    import subprocess
    import threading
    import time
    import webbrowser
    from tactus.ide import create_app

    setup_logging(verbose)

    # Save initial working directory before any chdir operations
    initial_workspace = os.getcwd()

    console.print(Panel("[bold blue]Starting Tactus IDE[/bold blue]", style="blue"))

    # Find available port for backend
    def find_available_port(preferred_port=None):
        """Find an available port, preferring the specified port if available."""
        if preferred_port:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", preferred_port))
                sock.close()
                return preferred_port
            except OSError:
                pass

        # Let OS assign an available port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        assigned_port = sock.getsockname()[1]
        sock.close()
        return assigned_port

    backend_port = find_available_port(port if port is not None else 5001)
    console.print(f"Server port: [cyan]{backend_port}[/cyan]")

    # Get paths - handle both development and PyInstaller frozen environments
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        frontend_dir = bundle_dir / "tactus-ide" / "frontend"
        dist_dir = frontend_dir / "dist"
    else:
        # Running in development
        project_root = Path(__file__).parent.parent.parent
        frontend_dir = project_root / "tactus-ide" / "frontend"
        dist_dir = frontend_dir / "dist"

    # Check if frontend is built
    if not dist_dir.exists():
        console.print("\n[yellow]Frontend not built. Building now...[/yellow]")

        if not frontend_dir.exists():
            console.print(f"[red]Error:[/red] Frontend directory not found: {frontend_dir}")
            raise typer.Exit(1)

        # Set environment variable for backend URL
        env = os.environ.copy()
        env["VITE_BACKEND_URL"] = f"http://localhost:{backend_port}"

        try:
            console.print("Running [cyan]npm run build[/cyan]...")
            result = subprocess.run(
                ["npm", "run", "build"], cwd=frontend_dir, env=env, capture_output=True, text=True
            )

            if result.returncode != 0:
                console.print(f"[red]Build failed:[/red]\n{result.stderr}")
                raise typer.Exit(1)

            console.print("[green]✓ Frontend built successfully[/green]\n")
        except FileNotFoundError:
            console.print("[red]Error:[/red] npm not found. Please install Node.js and npm.")
            raise typer.Exit(1)

    # Start backend server (which also serves frontend) in thread
    def run_backend():
        app = create_app(initial_workspace=initial_workspace, frontend_dist_dir=dist_dir)
        app.run(host="127.0.0.1", port=backend_port, debug=False, threaded=True, use_reloader=False)

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    console.print(f"[green]✓ Server started on http://127.0.0.1:{backend_port}[/green]")

    # Wait a moment for server to start
    time.sleep(1)

    # Open browser
    ide_url = f"http://localhost:{backend_port}"
    if not no_browser:
        console.print(f"\n[cyan]Opening browser to {ide_url}[/cyan]")
        webbrowser.open(ide_url)
    else:
        console.print(f"\n[cyan]IDE available at: {ide_url}[/cyan]")

    console.print("\n[dim]Press Ctrl+C to stop the IDE[/dim]\n")

    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down Tactus IDE...[/yellow]")
        console.print("[green]✓ IDE stopped[/green]")


@app.command(name="trace-list")
def trace_list(
    procedure: Optional[str] = typer.Option(None, help="Filter by procedure name"),
    status: Optional[str] = typer.Option(
        None, help="Filter by status (RUNNING, COMPLETED, FAILED)"
    ),
    limit: int = typer.Option(20, help="Maximum number of runs to display"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
):
    """List execution traces."""
    from tactus.tracing import TraceManager

    # Initialize storage
    if storage_path:
        storage = FileStorage(str(storage_path))
    else:
        storage = FileStorage()

    trace_mgr = TraceManager(storage)

    try:
        # Get runs
        runs = trace_mgr.list_runs(procedure_name=procedure, limit=limit)

        # Filter by status if specified
        if status:
            runs = [r for r in runs if r.status == status]

        if not runs:
            console.print("[yellow]No execution traces found[/yellow]")
            return

        # Display table
        table = Table(title="Execution Traces")
        table.add_column("Run ID", style="cyan", no_wrap=True)
        table.add_column("Procedure", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Started", style="blue")
        table.add_column("Duration")
        table.add_column("Checkpoints", justify="right")

        for run in runs:
            # Format duration
            if run.end_time:
                duration = run.end_time - run.start_time
                duration_str = f"{duration.total_seconds():.1f}s"
            else:
                duration_str = "running..."

            # Color status
            status_color = {
                "RUNNING": "yellow",
                "COMPLETED": "green",
                "FAILED": "red",
                "PAUSED": "blue",
            }.get(run.status, "white")

            table.add_row(
                run.run_id[:8],  # Show first 8 chars of run ID
                run.procedure_name,
                f"[{status_color}]{run.status}[/{status_color}]",
                run.start_time.strftime("%Y-%m-%d %H:%M"),
                duration_str,
                str(len(run.execution_log)),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing traces: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="trace-show")
def trace_show(
    run_id: str = typer.Argument(..., help="Run ID to display"),
    position: Optional[int] = typer.Option(None, help="Show specific checkpoint position"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
):
    """Show detailed trace information."""
    from tactus.tracing import TraceManager
    from rich.syntax import Syntax
    from rich.json import JSON

    # Initialize storage
    if storage_path:
        storage = FileStorage(str(storage_path))
    else:
        storage = FileStorage()

    trace_mgr = TraceManager(storage)

    try:
        run = trace_mgr.get_run(run_id)

        if position is not None:
            # Show specific checkpoint
            checkpoint = trace_mgr.get_checkpoint(run_id, position)

            console.print(Panel(f"[bold]Checkpoint {position}[/bold]", style="blue"))
            console.print(f"[cyan]Type:[/cyan] {checkpoint.type}")
            console.print(f"[cyan]Timestamp:[/cyan] {checkpoint.timestamp}")

            if checkpoint.duration_ms:
                console.print(f"[cyan]Duration:[/cyan] {checkpoint.duration_ms:.2f}ms")

            if checkpoint.source_location:
                console.print("\n[bold]Source Location:[/bold]")
                console.print(f"  [cyan]File:[/cyan] {checkpoint.source_location.file}")
                console.print(f"  [cyan]Line:[/cyan] {checkpoint.source_location.line}")
                if checkpoint.source_location.function:
                    console.print(f"  [cyan]Function:[/cyan] {checkpoint.source_location.function}")

                if checkpoint.source_location.code_context:
                    console.print("\n[bold]Code Context:[/bold]")
                    syntax = Syntax(
                        checkpoint.source_location.code_context,
                        "lua",
                        theme="monokai",
                        line_numbers=True,
                        start_line=checkpoint.source_location.line - 3,
                    )
                    console.print(syntax)

            if checkpoint.captured_vars:
                console.print("\n[bold]Captured State:[/bold]")
                console.print(JSON(str(checkpoint.captured_vars)))

            console.print("\n[bold]Result:[/bold]")
            console.print(JSON(str(checkpoint.result)))

        else:
            # Show full trace summary
            console.print(Panel(f"[bold]Execution Trace: {run_id}[/bold]", style="blue"))
            console.print(f"[cyan]Procedure:[/cyan] {run.procedure_name}")
            console.print(f"[cyan]File:[/cyan] {run.file_path}")
            console.print(f"[cyan]Status:[/cyan] {run.status}")
            console.print(f"[cyan]Started:[/cyan] {run.start_time}")

            if run.end_time:
                duration = run.end_time - run.start_time
                console.print(f"[cyan]Ended:[/cyan] {run.end_time}")
                console.print(f"[cyan]Duration:[/cyan] {duration.total_seconds():.2f}s")

            console.print(f"\n[bold]Checkpoints ({len(run.execution_log)}):[/bold]")

            # Show checkpoint table
            table = Table()
            table.add_column("Pos", justify="right", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Duration", justify="right")
            table.add_column("Source", style="blue")

            for cp in run.execution_log:
                duration_str = f"{cp.duration_ms:.1f}ms" if cp.duration_ms else "-"

                source_str = ""
                if cp.source_location:
                    source_str = f"{Path(cp.source_location.file).name}:{cp.source_location.line}"

                table.add_row(
                    str(cp.position),
                    cp.type,
                    duration_str,
                    source_str,
                )

            console.print(table)

            # Show statistics
            stats = trace_mgr.get_statistics(run_id)
            console.print("\n[bold]Statistics:[/bold]")
            console.print(f"  Total duration: {stats['total_duration_ms']:.2f}ms")
            console.print(f"  Checkpoints with source locations: {stats['has_source_locations']}")
            console.print("  Checkpoints by type:")
            for cp_type, count in stats["checkpoints_by_type"].items():
                console.print(f"    {cp_type}: {count}")

    except FileNotFoundError:
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)
    except IndexError:
        console.print(f"[red]Checkpoint position {position} out of range[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error showing trace: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="trace-export")
def trace_export(
    run_id: str = typer.Argument(..., help="Run ID to export"),
    output: Path = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("json", help="Export format (json)"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
):
    """Export trace to file."""
    from tactus.tracing import TraceManager

    # Initialize storage
    if storage_path:
        storage = FileStorage(str(storage_path))
    else:
        storage = FileStorage()

    trace_mgr = TraceManager(storage)

    try:
        data = trace_mgr.export_trace(run_id, format)

        output.write_text(data)

        console.print(f"[green]Exported trace to {output}[/green]")

    except FileNotFoundError:
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error exporting trace: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Stdlib Commands
# =============================================================================

stdlib_app = typer.Typer(help="Manage Tactus standard library")
app.add_typer(stdlib_app, name="stdlib")


@stdlib_app.command("test")
def stdlib_test(
    module: Optional[str] = typer.Argument(
        None, help="Specific module to test (e.g., 'classify', 'extract')"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    parallel: bool = typer.Option(True, "--parallel/--no-parallel", help="Run in parallel"),
):
    """
    Run BDD tests for standard library modules.

    Examples:
        tactus stdlib test              # Run all stdlib tests
        tactus stdlib test classify     # Run only classify tests
        tactus stdlib test extract      # Run only extract tests
    """
    import tactus
    from tactus.validation import TactusValidator
    from tactus.testing.test_runner import TactusTestRunner

    # Find stdlib spec files
    package_root = Path(tactus.__file__).parent
    stdlib_tac_path = package_root / "stdlib" / "tac" / "tactus"

    # Find all .spec.tac files
    if module:
        # Test specific module
        spec_file = stdlib_tac_path / f"{module}.spec.tac"
        if not spec_file.exists():
            console.print(f"[red]Module spec not found: {spec_file}[/red]")
            raise typer.Exit(1)
        spec_files = [spec_file]
    else:
        # Test all modules
        spec_files = list(stdlib_tac_path.glob("*.spec.tac"))

    if not spec_files:
        console.print("[yellow]No spec files found in stdlib[/yellow]")
        raise typer.Exit(0)

    console.print(f"[cyan]Found {len(spec_files)} spec file(s) to test[/cyan]")

    total_passed = 0
    total_failed = 0
    failed_modules = []

    validator = TactusValidator()

    for spec_file in sorted(spec_files):
        module_name = spec_file.stem.replace(".spec", "")
        console.print(f"\n[bold]Testing: {module_name}[/bold]")

        # Validate and load specs
        result = validator.validate_file(str(spec_file))

        if not result.valid:
            console.print("  [red]✗ Validation failed[/red]")
            for error in result.errors:
                console.print(f"    {error.message}")
            total_failed += 1
            failed_modules.append(module_name)
            continue

        if not result.registry or not result.registry.gherkin_specifications:
            console.print("  [yellow]⚠ No specifications found[/yellow]")
            continue

        # Run tests
        try:
            runner = TactusTestRunner(spec_file, mock_tools={}, params={})
            runner.setup(
                result.registry.gherkin_specifications,
                custom_steps_dict=result.registry.custom_steps,
            )

            test_result = runner.run_tests(parallel=parallel, scenario_filter=None)

            # Display results
            passed = test_result.passed_scenarios
            failed = test_result.failed_scenarios
            total_passed += passed
            total_failed += failed

            if failed > 0:
                console.print(f"  [red]✗ {passed} passed, {failed} failed[/red]")
                for feature in test_result.features:
                    for scenario in feature.scenarios:
                        if scenario.status != "failed":
                            continue
                        console.print(f"    [red]Scenario failed:[/red] {scenario.name}")
                        for step in scenario.steps:
                            if step.status != "failed":
                                continue
                            error_detail = step.error_message or "Unknown failure"
                            console.print(
                                f"      [red]{step.keyword} {step.message}[/red]: {error_detail}"
                            )
                failed_modules.append(module_name)
            else:
                console.print(f"  [green]✓ {passed} scenarios passed[/green]")

            runner.cleanup()

        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/red]")
            if verbose:
                console.print_exception()
            total_failed += 1
            failed_modules.append(module_name)

    # Summary
    console.print("\n" + "=" * 50)
    console.print("[bold]Stdlib Test Summary[/bold]")
    console.print(f"  Passed: [green]{total_passed}[/green]")
    console.print(f"  Failed: [red]{total_failed}[/red]")

    if failed_modules:
        console.print(f"\n[red]Failed modules: {', '.join(failed_modules)}[/red]")
        raise typer.Exit(1)

    console.print("\n[green]All stdlib tests passed![/green]")


# =============================================================================
# Control Command
# =============================================================================


@app.command()
def control(
    socket_path: Optional[str] = typer.Option(
        None,
        "--socket",
        "-s",
        help="Path to runtime's Unix socket (default: auto-detect from /tmp/tactus-control-*.sock)",
    ),
    auto_respond: Optional[str] = typer.Option(
        None, "--respond", "-r", help="Auto-respond with this value (for testing)"
    ),
):
    """
    Connect to running procedure and respond to control requests.

    Opens an interactive session that connects to a running Tactus procedure
    via Unix socket IPC. Control requests from Human.approve() and similar
    calls will appear here, and you can respond to them.

    This allows running the procedure in one terminal and responding to
    control requests from another terminal.
    """
    from tactus.cli.control import main as control_main
    import glob

    # Auto-detect socket path if not provided
    if socket_path is None:
        # Look for sockets in /tmp/tactus-control-*.sock
        socket_files = glob.glob("/tmp/tactus-control-*.sock")
        if not socket_files:
            console.print("[red]✗ No Tactus runtime sockets found[/red]")
            console.print("\n[yellow]Make sure a Tactus procedure is running:[/yellow]")
            console.print("  [dim]tactus run examples/90-hitl-simple.tac[/dim]")
            raise typer.Exit(1)
        elif len(socket_files) == 1:
            socket_path = socket_files[0]
            console.print(f"[dim]Auto-detected socket: {socket_path}[/dim]")
        else:
            console.print("[yellow]Multiple runtime sockets found:[/yellow]")
            for i, path in enumerate(socket_files, 1):
                console.print(f"  [{i}] {path}")
            console.print()
            selection = Prompt.ask(
                "Select socket",
                choices=[str(i) for i in range(1, len(socket_files) + 1)],
                default="1",
            )
            socket_path = socket_files[int(selection) - 1]

    # Run control CLI
    asyncio.run(control_main(socket_path, auto_respond))


def main():
    """Main entry point for the CLI."""
    # Load configuration before processing any commands
    load_tactus_config()

    # Check if user provided a direct file path (shortcut for 'run' command)
    # This allows: tactus procedure.tac instead of tactus run procedure.tac
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # Check if it's a file (not a subcommand or option)
        if not first_arg.startswith("-") and first_arg not in [
            "run",
            "validate",
            "test",
            "eval",
            "version",
            "ide",
            "stdlib",
            "control",
            "trace-list",
            "trace-show",
            "trace-export",
        ]:
            # Check if it's a file that exists
            potential_file = Path(first_arg)
            if potential_file.exists() and potential_file.is_file():
                # Insert 'run' command before the file path
                sys.argv.insert(1, "run")

    app()


if __name__ == "__main__":
    main()
