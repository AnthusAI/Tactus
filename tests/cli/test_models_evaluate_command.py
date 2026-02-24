import json
from pathlib import Path

from typer.testing import CliRunner

from tactus.cli.app import app

runner = CliRunner()


def _extract_json(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise AssertionError(f"No JSON output found in:\n{stdout}")


def _write_training_file(path: Path, fixture: Path) -> None:
    path.write_text(f"""
Model "imdb_nb" {{
  type = "registry",
  name = "imdb_nb",
  version = "latest",
  input = {{ text = "string" }},
  output = {{ label = "string", confidence = "float" }},
  training = {{
    data = {{
      source = "local",
      train = "{fixture}",
      test = "{fixture}",
      text_field = "text",
      label_field = "label"
    }},
    candidates = {{
      {{
        name = "nb-tfidf",
        trainer = "naive_bayes",
        hyperparameters = {{
          alpha = 1.0,
          max_features = 1000,
          ngram_min = 1,
          ngram_max = 1
        }}
      }}
    }}
  }}
}}
""")


def test_models_evaluate_by_version(tmp_path):
    fixture = Path(__file__).parent.parent / "fixtures" / "imdb_mini.jsonl"
    registry_dir = tmp_path / "registry"
    training_tac = tmp_path / "train.tac"
    _write_training_file(training_tac, fixture)

    train_result = runner.invoke(
        app,
        ["train", str(training_tac), "--registry-dir", str(registry_dir)],
    )
    assert train_result.exit_code == 0, train_result.stdout

    eval_result = runner.invoke(
        app,
        [
            "models",
            "evaluate",
            str(training_tac),
            "--model",
            "imdb_nb",
            "--version",
            "latest",
            "--registry-dir",
            str(registry_dir),
        ],
    )
    assert eval_result.exit_code == 0, eval_result.stdout
    payload = _extract_json(eval_result.stdout)
    assert payload["model"] == "imdb_nb"
    assert payload["version"] == "latest"
    assert payload["count"] > 0
    assert "metrics" in payload


def test_models_evaluate_by_candidate(tmp_path):
    fixture = Path(__file__).parent.parent / "fixtures" / "imdb_mini.jsonl"
    registry_dir = tmp_path / "registry"
    training_tac = tmp_path / "train.tac"
    _write_training_file(training_tac, fixture)

    train_result = runner.invoke(
        app,
        ["train", str(training_tac), "--registry-dir", str(registry_dir)],
    )
    assert train_result.exit_code == 0, train_result.stdout

    eval_result = runner.invoke(
        app,
        [
            "models",
            "evaluate",
            str(training_tac),
            "--model",
            "imdb_nb",
            "--candidate",
            "nb-tfidf",
            "--registry-dir",
            str(registry_dir),
        ],
    )
    assert eval_result.exit_code == 0, eval_result.stdout
    payload = _extract_json(eval_result.stdout)
    assert payload["model"] == "imdb_nb"
    assert payload["version"] == "candidate/nb-tfidf"
    assert payload["count"] > 0
    assert "metrics" in payload
