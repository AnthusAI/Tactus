"""
CLI commands for model registry management.
"""

from datetime import datetime
from typing import Optional

import typer

from tactus.registry.local import LocalRegistry

app = typer.Typer(help="Manage model registry and versions")


@app.command("list")
def list_versions(
    model_name: str = typer.Argument(..., help="Name of the model"),
    registry_dir: Optional[str] = typer.Option(
        None, help="Registry directory (default: ~/.tactus/models)"
    ),
):
    """List all versions of a model."""
    registry = LocalRegistry(registry_dir=registry_dir)

    try:
        versions = registry.list_versions(model_name)

        if not versions:
            typer.echo(f"No versions found for model '{model_name}'")
            return

        typer.echo(f"Versions for model '{model_name}':")
        typer.echo()

        # Header
        typer.echo(f"{'VERSION':<20} {'BACKEND':<15} {'TAGS':<30} {'CREATED':<25}")
        typer.echo("-" * 90)

        # Rows
        for version in versions:
            created_str = datetime.fromtimestamp(version.created_at).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            tags_str = ", ".join(version.tags) if version.tags else "-"

            typer.echo(
                f"{version.version_id:<20} "
                f"{version.backend_type:<15} "
                f"{tags_str:<30} "
                f"{created_str:<25}"
            )

        typer.echo()
        typer.echo(f"Total: {len(versions)} version(s)")

    except Exception as e:
        typer.echo(f"Error listing versions: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def promote(
    model_name: str = typer.Argument(..., help="Name of the model"),
    version: str = typer.Argument(..., help="Version identifier to promote"),
    tag: str = typer.Argument(..., help="Tag to apply (e.g., 'champion', 'staging')"),
    registry_dir: Optional[str] = typer.Option(
        None, help="Registry directory (default: ~/.tactus/models)"
    ),
):
    """
    Promote a model version by applying a tag.

    If the tag already exists, it will be moved to the new version,
    and the previous version will be tagged as '{tag}-previous'.
    """
    registry = LocalRegistry(registry_dir=registry_dir)

    try:
        registry.promote(model_name, version, tag)
        typer.secho(f"✓ Promoted {model_name} version {version} to tag '{tag}'", fg=typer.colors.GREEN)

        # Show what happened
        try:
            previous = registry.resolve(model_name, f"{tag}-previous")
            typer.echo(
                f"  Previous {tag} version {previous.version_id} "
                f"tagged as '{tag}-previous'"
            )
        except ValueError:
            pass  # No previous version

    except ValueError as e:
        typer.echo(f"Error promoting version: {e}", err=True)
        raise typer.Exit(1)
