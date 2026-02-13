from tactus.backends.ensemble_backend import ABTestBackend, EnsembleBackend, MockBackend


def test_ensemble_vote_majority():
    backend = EnsembleBackend(
        backends=[MockBackend("A"), MockBackend("B"), MockBackend("A")],
        strategy="vote",
    )
    result = backend.predict_sync({"x": 1})
    assert result["result"] == "A"


def test_ensemble_average():
    backend = EnsembleBackend(
        backends=[MockBackend(1.0), MockBackend(2.0), MockBackend(3.0)],
        strategy="average",
    )
    result = backend.predict_sync({"x": 1})
    assert result["result"] == 2.0


def test_ab_test_weighting_deterministic():
    backend = ABTestBackend(
        backends=[MockBackend("A"), MockBackend("B")],
        weights=[0.0, 1.0],
        seed=123,
    )
    output = backend.predict_sync({"x": 1})
    assert output["result"] == "B"
    assert output["meta"]["arm_index"] == 1
