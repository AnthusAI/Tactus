"""
Tactus CLI Application.

Main entry point for the Tactus command-line interface.
Provides commands for running, validating, and testing workflows.
"""

import asyncio
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
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tactus.lua or .tyml)"),
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

    # Determine format based on extension
    file_format = "lua" if workflow_file.suffix == ".lua" else "yaml"

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
        openai_api_key=api_key,
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
    workflow_file: Path = typer.Argument(..., help="Path to workflow file (.tactus.lua or .tyml)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quick: bool = typer.Option(False, "--quick", help="Quick validation (syntax only)"),
):
    """
    Validate a Tactus workflow file.

    Examples:

        tactus validate workflow.tactus.lua
        tactus validate workflow.tyml  # Legacy YAML format
        tactus validate workflow.tactus.lua --quick
    """
    setup_logging(verbose)

    # Check if file exists
    if not workflow_file.exists():
        console.print(f"[red]Error:[/red] Workflow file not found: {workflow_file}")
        raise typer.Exit(1)

    # Determine format based on extension
    file_format = "lua" if workflow_file.suffix == ".lua" else "yaml"

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

                if result.registry:
                    # Convert registry to config dict for display
                    config = {
                        "name": result.registry.procedure_name,
                        "version": result.registry.version,
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
    import http.server
    import socketserver
    from tactus.ide import create_app

    setup_logging(verbose)

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
    console.print(f"Backend port: [cyan]{backend_port}[/cyan]")

    # Find available port for frontend
    frontend_port_actual = find_available_port(frontend_port)
    if frontend_port_actual != frontend_port:
        console.print(
            f"[yellow]Note: Port {frontend_port} in use, using {frontend_port_actual}[/yellow]"
        )
    console.print(f"Frontend port: [cyan]{frontend_port_actual}[/cyan]")

    # Get paths
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

    # Start backend server in thread
    def run_backend():
        app = create_app()
        app.run(host="127.0.0.1", port=backend_port, debug=False, threaded=True, use_reloader=False)

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    console.print(f"[green]✓ Backend server started on http://127.0.0.1:{backend_port}[/green]")

    # Start frontend server in thread
    def run_frontend():
        os.chdir(dist_dir)
        handler = http.server.SimpleHTTPRequestHandler

        # Suppress HTTP server logs unless verbose
        if not verbose:
            handler.log_message = lambda *args: None

        with socketserver.TCPServer(("", frontend_port_actual), handler) as httpd:
            httpd.serve_forever()

    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    frontend_thread.start()
    console.print(
        f"[green]✓ Frontend server started on http://localhost:{frontend_port_actual}[/green]"
    )

    # Wait a moment for servers to start
    time.sleep(1)

    # Open browser
    frontend_url = f"http://localhost:{frontend_port_actual}"
    if not no_browser:
        console.print(f"\n[cyan]Opening browser to {frontend_url}[/cyan]")
        webbrowser.open(frontend_url)
    else:
        console.print(f"\n[cyan]IDE available at: {frontend_url}[/cyan]")

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
