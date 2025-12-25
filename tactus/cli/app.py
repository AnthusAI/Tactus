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
    Load Tactus configuration from .tactus/config.yml using dotyaml.

    This will:
    - Load configuration from .tactus/config.yml if it exists
    - Set environment variables from the config (e.g., openai_api_key -> OPENAI_API_KEY)
    - Also automatically loads .env file if present (via dotyaml)

    Returns:
        dict: Configuration dictionary, or empty dict if no config found
    """
    config_path = Path.cwd() / ".tactus" / "config.yml"

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
            import json

            for key, value in config_dict.items():
                # Skip mcp_servers - we'll pass it directly to runtime
                if key == "mcp_servers":
                    continue

                if isinstance(value, (str, int, float, bool)):
                    env_key = key.upper()
                    # Only set if not already set (env vars take precedence)
                    if env_key not in os.environ:
                        os.environ[env_key] = str(value)
                elif isinstance(value, list):
                    # Handle lists by serializing to JSON
                    # e.g., tool_paths: ["./tools"] -> TOOL_PATHS='["./tools"]'
                    env_key = key.upper()
                    if env_key not in os.environ:
                        os.environ[env_key] = json.dumps(value)
                elif isinstance(value, dict):
                    # Handle nested structures by flattening with underscores
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, (str, int, float, bool)):
                            env_key = f"{key.upper()}_{nested_key.upper()}"
                            if env_key not in os.environ:
                                os.environ[env_key] = str(nested_value)

            return config_dict
        except Exception as e:
            # Don't fail if config loading fails - just log and continue
            logging.debug(f"Could not load config from {config_path}: {e}")
            return {}

    return {}


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

    # Override context params with CLI params (CLI takes precedence)
    if param:
        # Merge: CLI params override config params
        for p in param:
            if "=" in p:
                key, value = p.split("=", 1)
                context[key] = value

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
        mcp_server=None,  # Legacy parameter (deprecated)
        mcp_servers=mcp_servers,  # New multi-server support
        openai_api_key=api_key,
        log_handler=log_handler,
        tool_paths=tool_paths,
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
                    for name, output in result.registry.output_schema.items():
                        config["outputs"][name] = {
                            "type": output.get("type", "string"),
                            "required": output.get("required", False),
                        }
                    for name, param in result.registry.input_schema.items():
                        config["params"][name] = {
                            "type": param.get("type", "string"),
                            "required": param.get("required", False),
                            "default": param.get("default"),
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
            evaluator.setup(result.registry.gherkin_specifications)

            if scenario:
                eval_results = [evaluator.evaluate_scenario(scenario, runs, parallel)]
            else:
                eval_results = evaluator.evaluate_all(runs, parallel)

            _display_evaluation_results(eval_results)
            evaluator.cleanup()

        else:
            # Run standard test
            runner = TactusTestRunner(procedure_file, mock_tools=mock_tools, params=test_params)
            runner.setup(result.registry.gherkin_specifications)

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
        ]:
            # Check if it's a file that exists
            potential_file = Path(first_arg)
            if potential_file.exists() and potential_file.is_file():
                # Insert 'run' command before the file path
                sys.argv.insert(1, "run")

    app()


if __name__ == "__main__":
    main()
