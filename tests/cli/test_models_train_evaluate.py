import json
import tempfile
from pathlib import Path

import pytest

from typer.testing import CliRunner

from tactus.cli.commands.models import app

runner = CliRunner()


def test_train_runs_candidates():
    with tempfile.TemporaryDirectory() as tmpdir:
        script = Path(tmpdir) / "train.py"
        script.write_text(
            "import json\n"
            "print(json.dumps({'accuracy':0.9,'loss':0.1}))\n"
        )

        config = {
            "model_name": "demo",
            "train": "data/train.jsonl",
            "candidates": [
                {
                    "name": "c1",
                    "type": "pytorch",
                    "training": {"script": str(script)},
                }
            ],
        }
        config_path = Path(tmpdir) / "config.json"
        config_path.write_text(json.dumps(config))

        result = runner.invoke(app, ["train", str(config_path)])
        assert result.exit_code == 0, result.stdout
        assert "c1" in result.stdout


def test_evaluate_outputs_metrics(tmp_path):
    preds = ["positive", "negative", "positive"]
    labels = ["positive", "negative", "negative"]

    preds_path = tmp_path / "preds.json"
    labels_path = tmp_path / "labels.json"
    preds_path.write_text(json.dumps(preds))
    labels_path.write_text(json.dumps(labels))

    result = runner.invoke(app, ["evaluate", str(preds_path), str(labels_path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "accuracy" in data
    assert data["accuracy"] == pytest.approx(2 / 3)
