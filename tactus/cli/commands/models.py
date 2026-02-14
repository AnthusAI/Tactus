"""
CLI commands for model registry management.
"""

from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

import typer
from rich.console import Console
from rich.table import Table

from tactus.registry.local import LocalRegistry

app = typer.Typer(help="Manage model registry and versions")
console = Console()


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
            created_str = datetime.fromtimestamp(version.created_at).strftime("%Y-%m-%d %H:%M:%S")
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
        typer.secho(
            f"✓ Promoted {model_name} version {version} to tag '{tag}'", fg=typer.colors.GREEN
        )

        # Show what happened
        try:
            previous = registry.resolve(model_name, f"{tag}-previous")
            typer.echo(
                f"  Previous {tag} version {previous.version_id} " f"tagged as '{tag}-previous'"
            )
        except ValueError:
            pass  # No previous version

    except ValueError as e:
        typer.echo(f"Error promoting version: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def evaluate(
    training_file: str = typer.Argument(..., help="Path to training config (.tac)"),
    model: Optional[str] = typer.Option(None, "--model", help="Model name if multiple exist"),
    version: Optional[str] = typer.Option(None, "--version", help="Version or tag to evaluate"),
    candidate: Optional[str] = typer.Option(None, "--candidate", help="Candidate name to evaluate"),
    registry_dir: Optional[str] = typer.Option(
        None, help="Registry directory (default: ~/.tactus/models)"
    ),
):
    """
    Evaluate a trained model against the test split defined in training config.
    """
    if version and candidate:
        typer.echo("Error: Specify only one of --version or --candidate", err=True)
        raise typer.Exit(1)

    try:
        import json
        from pathlib import Path

        from tactus.backends.registry_backend import RegistryBackend
        from tactus.training.config import load_training_config
        from tactus.training.datasets import load_dataset_bundle

        training_path = Path(training_file)
        if not training_path.exists():
            typer.echo(f"Error: Training file not found: {training_file}", err=True)
            raise typer.Exit(1)
        if training_path.suffix not in [".tac", ".lua"]:
            typer.echo("Error: Training config must be a .tac file", err=True)
            raise typer.Exit(1)

        config = load_training_config(str(training_path), model_name=model)
        if not config.data.test:
            typer.echo("Error: training.data.test is required for evaluation", err=True)
            raise typer.Exit(1)

        data_bundle = load_dataset_bundle(config.data)
        if not data_bundle.test:
            typer.echo("Error: Test split is empty; cannot evaluate", err=True)
            raise typer.Exit(1)

        registry = LocalRegistry(registry_dir=registry_dir)
        version_tag = version or (f"candidate/{candidate}" if candidate else "latest")

        backend = RegistryBackend(
            registry=registry,
            model_name=config.model_name,
            version=version_tag,
        )

        y_true = [row.get("label") for row in data_bundle.test]
        y_pred = []
        for row in data_bundle.test:
            pred = backend.predict_sync({"text": row.get("text")})
            if isinstance(pred, dict):
                y_pred.append(pred.get("label"))
            else:
                y_pred.append(pred)

        y_true, y_pred = _normalize_labels(y_true, y_pred)
        metrics = _compute_metrics(y_true, y_pred)

        result = {
            "model": config.model_name,
            "version": version_tag,
            "count": len(y_true),
            "metrics": metrics,
        }

        _print_metrics_table(result)
        typer.echo(json.dumps(result))

    except Exception as e:
        typer.echo(f"Error evaluating model: {e}", err=True)
        raise typer.Exit(1)


def _normalize_labels(
    y_true: List[Any], y_pred: List[Any]
) -> Tuple[List[str], List[str]]:
    def to_str(value: Any) -> str:
        return value if isinstance(value, str) else str(value)

    true_set = {to_str(v) for v in y_true}
    pred_set = {to_str(v) for v in y_pred}

    numeric_labels = {"0", "1"}
    text_labels = {"negative", "positive"}

    if true_set.issubset(numeric_labels) and pred_set.issubset(text_labels):
        mapping = {"0": "negative", "1": "positive"}
        y_true = [mapping.get(to_str(v), to_str(v)) for v in y_true]
        y_pred = [to_str(v) for v in y_pred]
        return y_true, y_pred

    if pred_set.issubset(numeric_labels) and true_set.issubset(text_labels):
        mapping = {"0": "negative", "1": "positive"}
        y_pred = [mapping.get(to_str(v), to_str(v)) for v in y_pred]
        y_true = [to_str(v) for v in y_true]
        return y_true, y_pred

    return [to_str(v) for v in y_true], [to_str(v) for v in y_pred]


def _compute_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, float]:
    try:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    except ImportError as exc:
        raise ImportError("scikit-learn not installed. Install with: pip install tactus[ml]") from exc

    labels = sorted(set(y_true) | set(y_pred))
    if len(labels) <= 2:
        pos_label = "positive" if "positive" in labels else labels[-1]
        precision = precision_score(y_true, y_pred, average="binary", pos_label=pos_label, zero_division=0)
        recall = recall_score(y_true, y_pred, average="binary", pos_label=pos_label, zero_division=0)
        f1 = f1_score(y_true, y_pred, average="binary", pos_label=pos_label, zero_division=0)
    else:
        precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def _print_metrics_table(result: Dict[str, Any]) -> None:
    metrics = result["metrics"]
    table = Table(title="Evaluation Metrics")
    table.add_column("Model", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("Count", style="yellow")
    table.add_column("Accuracy")
    table.add_column("Precision")
    table.add_column("Recall")
    table.add_column("F1")

    table.add_row(
        result["model"],
        result["version"],
        str(result["count"]),
        f"{metrics['accuracy']:.4f}",
        f"{metrics['precision']:.4f}",
        f"{metrics['recall']:.4f}",
        f"{metrics['f1']:.4f}",
    )

    console.print(table)
