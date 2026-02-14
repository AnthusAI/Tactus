import json
from pathlib import Path

from typer.testing import CliRunner

from tactus.cli.app import app

runner = CliRunner()


def test_train_command_runs(tmp_path):
    fixture = Path(__file__).parent.parent / "fixtures" / "imdb_mini.jsonl"
    registry_dir = tmp_path / "registry"

    training_tac = tmp_path / "train.tac"
    training_tac.write_text(
        f"""
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
"""
    )

    result = runner.invoke(
        app,
        ["train", str(training_tac), "--registry-dir", str(registry_dir)],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "nb-tfidf" in payload
