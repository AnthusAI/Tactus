"""
Tactus CLI Application.

Main entry point for the Tactus command-line interface.
Provides commands for running, validating, and testing workflows.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional
import logging

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from dotyaml import load_config

from tactus.core import TactusRuntime
from tactus.core.yaml_parser import ProcedureYAMLParser, ProcedureConfigError
from tactus.adapters.memory import MemoryStorage
from tactus.adapters.file_storage import FileStorage
from tactus.adapters.cli_hitl import CLIHITLHandler

# Setup rich console for pretty output
console = Console()

# Create Typer app
app = typer.Typer(
    name="tactus",
    help="Tactus - Workflow automation with Lua DSL",
    add_completion=False
)


def load_tactus_config():
    """
    Load Tactus configuration from .tactus/config.yml using dotyaml.
    
    This will:
    - Load configuration from .tactus/config.yml if it exists
    - Set environment variables from the config (e.g., openai_api_key -> OPENAI_API_KEY)
    - Also automatically loads .env file if present (via dotyaml)
    """
    config_path = Path.cwd() / ".tactus" / "config.yml"
    
    if config_path.exists():
        try:
            # Load config without prefix - this means top-level keys become env vars directly
            # e.g., openai_api_key in YAML -> OPENAI_API_KEY env var
            load_config(str(config_path), prefix='')
            
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
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)]
    )


@app.command()
def run(
    workflow_file: Path = typer.Argument(..., help="Path to workflow YAML file"),
    storage: str = typer.Option("memory", help="Storage backend: memory, file"),
    storage_path: Optional[Path] = typer.Option(None, help="Path for file storage"),
    openai_api_key: Optional[str] = typer.Option(None, envvar="OPENAI_API_KEY", help="OpenAI API key"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    param: Optional[list[str]] = typer.Option(None, help="Parameters in format key=value")
):
    """
    Run a Tactus workflow.

    Examples:

        # Run with memory storage
        tactus run workflow.yaml

        # Run with file storage
        tactus run workflow.yaml --storage file --storage-path ./data

        # Pass parameters
        tactus run workflow.yaml --param task="Analyze data" --param count=5
    """
    setup_logging(verbose)

    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Read workflow YAML
    yaml_content = workflow_file.read_text()

    # Parse parameters
    context = {}
    if param:
        for p in param:
            if '=' not in p:
                console.print(f"[red]Error:[/red] Invalid parameter format: {p} (expected key=value)")
                raise typer.Exit(1)
            key, value = p.split('=', 1)
            context[key] = value

    # Setup storage backend
    if storage == "memory":
        storage_backend = MemoryStorage()
    elif storage == "file":
        if not storage_path:
            storage_path = Path.cwd() / ".tactus" / "storage"
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

    # Create runtime
    procedure_id = f"cli-{workflow_file.stem}"
    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=storage_backend,
        hitl_handler=hitl_handler,
        chat_recorder=None,  # No chat recording in CLI mode
        mcp_server=None,  # No MCP server in basic CLI mode
        openai_api_key=api_key
    )

    # Execute procedure
    console.print(Panel(f"Running procedure: [bold]{workflow_file.name}[/bold]", style="blue"))

    try:
        result = asyncio.run(runtime.execute(yaml_content, context))

        if result['success']:
            console.print("\n[green]✓ Procedure completed successfully[/green]\n")

            # Display results
            if result.get('result'):
                console.print(Panel(str(result['result']), title="Result", style="green"))

            # Display state
            if result.get('state'):
                state_table = Table(title="Final State")
                state_table.add_column("Key", style="cyan")
                state_table.add_column("Value", style="magenta")

                for key, value in result['state'].items():
                    state_table.add_row(key, str(value))

                console.print(state_table)

            # Display stats
            console.print(f"\n[dim]Iterations: {result.get('iterations', 0)}[/dim]")
            console.print(f"[dim]Tools used: {', '.join(result.get('tools_used', [])) or 'None'}[/dim]")

        else:
            console.print(f"\n[red]✗ Workflow failed[/red]\n")
            if result.get('error'):
                console.print(f"[red]Error: {result['error']}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Execution error: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def validate(
    workflow_file: Path = typer.Argument(..., help="Path to workflow YAML file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    Validate a Tactus workflow YAML file.

    Examples:

        tactus validate workflow.yaml
    """
    setup_logging(verbose)

    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Read workflow YAML
    yaml_content = workflow_file.read_text()

    console.print(f"Validating: [bold]{workflow_file.name}[/bold]")

    try:
        # Parse YAML
        config = ProcedureYAMLParser.parse(yaml_content)

        # Display validation results
        console.print("\n[green]✓ YAML is valid[/green]\n")

        # Show config details
        info_table = Table(title="Workflow Info")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="magenta")

        info_table.add_row("Name", config.get('name', 'N/A'))
        info_table.add_row("Version", config.get('version', 'N/A'))
        info_table.add_row("Class", config.get('class', 'LuaDSL'))

        if config.get('description'):
            info_table.add_row("Description", config['description'])

        console.print(info_table)

        # Show agents
        if config.get('agents'):
            agents_table = Table(title="Agents")
            agents_table.add_column("Name", style="cyan")
            agents_table.add_column("System Prompt", style="magenta")

            for name, agent_config in config['agents'].items():
                prompt = agent_config.get('system_prompt', 'N/A')
                # Truncate long prompts
                if len(prompt) > 50:
                    prompt = prompt[:47] + "..."
                agents_table.add_row(name, prompt)

            console.print(agents_table)

        # Show outputs
        if config.get('outputs'):
            outputs_table = Table(title="Outputs")
            outputs_table.add_column("Name", style="cyan")
            outputs_table.add_column("Type", style="magenta")
            outputs_table.add_column("Required", style="yellow")

            for name, output_config in config['outputs'].items():
                outputs_table.add_row(
                    name,
                    output_config.get('type', 'any'),
                    "✓" if output_config.get('required', False) else ""
                )

            console.print(outputs_table)

        # Show parameters
        if config.get('params'):
            params_table = Table(title="Parameters")
            params_table.add_column("Name", style="cyan")
            params_table.add_column("Type", style="magenta")
            params_table.add_column("Default", style="yellow")

            for name, param_config in config['params'].items():
                params_table.add_row(
                    name,
                    param_config.get('type', 'any'),
                    str(param_config.get('default', ''))
                )

            console.print(params_table)

        console.print("\n[green]Validation complete![/green]")

    except ProcedureConfigError as e:
        console.print(f"\n[red]✗ Validation failed:[/red]\n")
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error:[/red]\n")
        console.print(f"[red]{e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def version():
    """Show Tactus version."""
    from tactus import __version__
    console.print(f"Tactus version: [bold]{__version__}[/bold]")


def main():
    """Main entry point for the CLI."""
    # Load configuration before processing any commands
    load_tactus_config()
    app()


if __name__ == "__main__":
    main()
