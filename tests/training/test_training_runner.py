from pathlib import Path

from tactus.training.datasets import DatasetBundle
from tactus.training.runner import TrainingRunner
from tactus.training.trainers import TrainerRegistry
from tactus.training.types import CandidateConfig, TrainedModel, TrainingConfig, TrainingDataConfig


def test_training_runner_zips_directory_artifacts(monkeypatch, tmp_path):
    class FakeTrainer:
        name = "fake_dir"

        def train(self, candidate, data, workdir):
            artifact_dir = Path(workdir) / candidate.name
            artifact_dir.mkdir()
            (artifact_dir / "model.bin").write_text("ok")
            return TrainedModel(
                artifact_path=str(artifact_dir),
                backend_type="fake",
                backend_config={"path": str(artifact_dir)},
                metrics=None,
            )

    registry = TrainerRegistry()
    registry.register(FakeTrainer())

    monkeypatch.setattr("tactus.training.runner._register_default_trainers", lambda: None)
    monkeypatch.setattr("tactus.training.runner.get_trainer_registry", lambda: registry)
    monkeypatch.setattr(
        "tactus.training.runner.load_dataset_bundle",
        lambda cfg: DatasetBundle(train=[{"text": "x", "label": 0}], val=None, test=None),
    )

    runner = TrainingRunner(registry_dir=str(tmp_path / "registry"))
    config = TrainingConfig(
        model_name="demo",
        data=TrainingDataConfig(
            source="local",
            name=None,
            train="unused",
            val=None,
            test=None,
            text_field="text",
            label_field="label",
        ),
        candidates=[CandidateConfig(name="fake", trainer="fake_dir", hyperparameters={})],
        input=None,
        output=None,
    )

    runner.run(config, register=True, evaluate=False)

    versions = runner.registry.list_versions("demo")
    assert versions
    artifact_path = versions[0].artifact_path
    assert artifact_path is not None
    assert artifact_path.endswith(".zip")
    assert Path(artifact_path).is_file()
