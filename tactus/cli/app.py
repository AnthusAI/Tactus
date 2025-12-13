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
from pathlib import Path
from typing import Optional
import logging
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from dotyaml import load_config

from tactus.core import TactusRuntime
from tactus.core.yaml_parser import ProcedureYAMLParser, ProcedureConfigError
from tactus.validation import TactusValidator, ValidationMode
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage
from tactus.adapters.cli_hitl import CLIHITLHandler

# Setup rich console for pretty output
console = Console()

# Create Typer app
app = typer.Typer(
    name="tactus", help="Tactus - Workflow automation with Lua DSL", add_completion=False
)


def load_tactus_config():
    """
    Load Tactus configuration from .tac/config.yml using dotyaml.

    This will:
    - Load configuration from .tac/config.yml if it exists
    - Set environment variables from the config (e.g., openai_api_key -> OPENAI_API_KEY)
    - Also automatically loads .env file if present (via dotyaml)
    """
    config_path = Path.cwd() / ".tac" / "config.yml"

    if config_path.exists():
        try:
            # Load config without prefix - this means top-level keys become env vars directly
            # e.g., openai_api_key in YAML -> OPENAI_API_KEY env var
            load_config(str(config_path), prefix="")

            # Explicitly uppercase any keys that need to be env vars
            # Since we're using prefix='', dotyaml will create env vars with exact key names
            # But we need to ensure uppercase for standard env var conventions
            # Read the config manually to uppercase the keys
            import yaml

            with open(config_path) as f:
                config_dict = yaml.safe_load(f) or {}

            # Set uppercase env vars for any keys in the config
            # This ensures openai_api_key -> OPENAI_API_KEY
            for key, value in config_dict.items():
                if isinstance(value, (str, int, float, bool)):
                    env_key = key.upper()
                    # Only set if not already set (env vars take precedence)
                    if env_key not in os.environ:
                        os.environ[env_key] = str(value)
                elif isinstance(value, dict):
                    # Handle nested structures by flattening with underscores
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, (str, int, float, bool)):
                            env_key = f"{key.upper()}_{nested_key.upper()}"
                            if env_key not in os.environ:
                                os.environ[env_key] = str(nested_value)
        except Exception as e:
            # Don't fail if config loading fails - just log and continue
            logging.debug(f"Could not load config from {config_path}: {e}")


def setup_logging(verbose: bool = False):
    """Setup logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )


@app.command()
def run(
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tac)"),
    storage: str = typer.Option("memory", help="Storage backend: memory, file"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
    openai_api_key: Optional[str] = typer.Option(
        None, envvar="OPENAI_API_KEY", help="OpenAI API key"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value"),
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

    # Parse parameters
    context = {}
    if param:
        for p in param:
            if "=" not in p:
                console.print(
                    f"[red]Error:[/red] Invalid parameter format: {p} (expected key=value)"
                )
                raise typer.Exit(1)
            key, value = p.split("=", 1)
            context[key] = value

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

    # Setup HITL handler
    hitl_handler = CLIHITLHandler(console=console)

    # Get OpenAI API key from parameter, environment, or config
    # Parameter takes precedence, then env var, then config
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    # Create log handler for Rich formatting
    from tactus.adapters.cli_log import CLILogHandler

    log_handler = CLILogHandler(console)

    # Suppress verbose runtime logging when using structured log handler
    # This prevents duplicate output - we only want the clean structured logs
    logging.getLogger("tactus.core.runtime").setLevel(logging.WARNING)
    logging.getLogger("tactus.primitives").setLevel(logging.WARNING)

    # Create runtime
    procedure_id = f"cli-{workflow_file.stem}"
    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=storage_backend,
        hitl_handler=hitl_handler,
        chat_recorder=None,  # No chat recording in CLI mode
        mcp_server=None,  # No MCP server in basic CLI mode
        openai_api_key=api_key,
        log_handler=log_handler,
    )

    # Execute procedure
    console.print(
        Panel(
            f"Running procedure: [bold]{workflow_file.name}[/bold] ({file_format} format)",
            style="blue",
        )
    )

    try:
        result = asyncio.run(runtime.execute(source_content, context, format=file_format))

        if result["success"]:
            console.print("\n[green]✓ Procedure completed successfully[/green]\n")

            # Display results
            if result.get("result"):
                console.print(Panel(str(result["result"]), title="Result", style="green"))

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
                        "outputs": {},
                        "params": {},
                    }
                    # Convert Pydantic models to dicts
                    for name, agent in result.registry.agents.items():
                        config["agents"][name] = {
                            "system_prompt": agent.system_prompt,
                            "provider": agent.provider,
                            "model": agent.model,
                        }
                    for name, output in result.registry.outputs.items():
                        config["outputs"][name] = {
                            "type": output.field_type.value,
                            "required": output.required,
                        }
                    for name, param in result.registry.parameters.items():
                        config["params"][name] = {
                            "type": param.parameter_type.value,
                            "required": param.required,
                            "default": param.default,
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
        if config.get("outputs"):
            outputs_table = Table(title="Outputs")
            outputs_table.add_column("Name", style="cyan")
            outputs_table.add_column("Type", style="magenta")
            outputs_table.add_column("Required", style="yellow")

            for name, output_config in config["outputs"].items():
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


@app.command()
def test(
    procedure_file: Path = typer.Argument(..., help="Path to procedure file (.tac or .lua)"),
    scenario: Optional[str] = typer.Option(None, help="Run specific scenario"),
    parallel: bool = typer.Option(True, help="Run scenarios in parallel"),
    mock: bool = typer.Option(False, help="Use mocked tools (fast, deterministic)"),
    mock_config: Optional[Path] = typer.Option(None, help="Path to mock config JSON"),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Run BDD specifications for a procedure.

    Examples:

        # Run all scenarios
        tactus test procedure.tac

        # Run with mocked tools (fast, no API calls)
        tactus test procedure.tac --mock

        # Run with custom mock config
        tactus test procedure.tac --mock-config mocks.json

        # Run specific scenario
        tactus test procedure.tac --scenario "Agent completes research"

        # Pass parameters
        tactus test procedure.tac --param topic="AI" --param count=5

        # Run sequentially (no parallel)
        tactus test procedure.tac --no-parallel
    """
    setup_logging(verbose)

    if not procedure_file.exists():
        console.print(f"[red]Error:[/red] File not found: {procedure_file}")
        raise typer.Exit(1)

    mode_str = "mocked" if (mock or mock_config) else "real"
    console.print(Panel(f"Running BDD Tests ({mode_str} mode)", style="blue"))

    try:
        from tactus.testing.test_runner import TactusTestRunner
        from tactus.testing.mock_tools import create_default_mocks
        from tactus.validation import TactusValidator
        import json

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

        # Setup and run tests
        runner = TactusTestRunner(procedure_file, mock_tools=mock_tools, params=test_params)
        runner.setup(result.registry.gherkin_specifications)

        test_result = runner.run_tests(parallel=parallel, scenario_filter=scenario)

        # Display results
        _display_test_results(test_result)

        # Cleanup
        runner.cleanup()

        # Exit with appropriate code
        if test_result.failed_scenarios > 0:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def evaluate(
    procedure_file: Path = typer.Argument(..., help="Path to procedure file (.tac or .lua)"),
    runs: int = typer.Option(10, help="Number of runs per scenario"),
    scenario: Optional[str] = typer.Option(None, help="Evaluate specific scenario"),
    parallel: bool = typer.Option(True, help="Run in parallel"),
    workers: Optional[int] = typer.Option(None, help="Number of parallel workers"),
    mock: bool = typer.Option(False, help="Use mocked tools (fast, deterministic)"),
    mock_config: Optional[Path] = typer.Option(None, help="Path to mock config JSON"),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """
    Evaluate procedure consistency by running specs multiple times.

    Examples:

        # Evaluate with 10 runs per scenario
        tactus evaluate procedure.tac --runs 10

        # Evaluate with mocked tools
        tactus evaluate procedure.tac --runs 50 --mock

        # Evaluate with custom mock config
        tactus evaluate procedure.tac --runs 20 --mock-config mocks.json

        # Evaluate specific scenario
        tactus evaluate procedure.tac --scenario "Agent completes research"
    """
    setup_logging(verbose)

    if not procedure_file.exists():
        console.print(f"[red]Error:[/red] File not found: {procedure_file}")
        raise typer.Exit(1)

    mode_str = "mocked" if (mock or mock_config) else "real"
    console.print(
        Panel(f"Running Evaluation ({runs} runs per scenario, {mode_str} mode)", style="blue")
    )

    try:
        from tactus.testing.evaluation_runner import TactusEvaluationRunner
        from tactus.testing.mock_tools import create_default_mocks
        from tactus.validation import TactusValidator
        import json

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

        # Setup and run evaluation
        evaluator = TactusEvaluationRunner(
            procedure_file, mock_tools=mock_tools, params=test_params
        )
        evaluator.setup(result.registry.gherkin_specifications)

        if scenario:
            # Evaluate single scenario
            eval_results = [evaluator.evaluate_scenario(scenario, runs, parallel)]
        else:
            # Evaluate all scenarios
            eval_results = evaluator.evaluate_all(runs, parallel)

        # Display results
        _display_evaluation_results(eval_results)

        # Cleanup
        evaluator.cleanup()

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
                        console.print(f"    [red]Failed:[/red] {step.keyword} {step.text}")
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
            f"  Duration: {eval_result.mean_duration:.2f}s "
            f"(±{eval_result.stddev_duration:.2f}s)"
        )

        # Consistency
        consistency_color = "green" if eval_result.consistency_score >= 0.9 else "yellow"
        console.print(
            f"  Consistency: [{consistency_color}]{eval_result.consistency_score:.1%}[/{consistency_color}]"
        )

        # Flakiness warning
        if eval_result.is_flaky:
            console.print("  [yellow]⚠️  FLAKY - Inconsistent results detected[/yellow]")


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

    backend_port = find_available_port(port or 5001)
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


def main():
    """Main entry point for the CLI."""
    # Load configuration before processing any commands
    load_tactus_config()
    app()


if __name__ == "__main__":
    main()
