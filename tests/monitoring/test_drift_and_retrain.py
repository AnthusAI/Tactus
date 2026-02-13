from tactus.monitoring.drift import RollingDriftDetector, detect_mean_shift
from tactus.monitoring.retrain import should_trigger_retrain


def test_rolling_drift_detector():
    detector = RollingDriftDetector(window=4, threshold_pct=0.5)
    assert detector.update("aaaa") is False
    assert detector.update("aaaa") is False
    # Large shift
    assert detector.update("a" * 20) is True


def test_detect_mean_shift():
    assert detect_mean_shift([1, 1, 1], [2, 2, 2], threshold_pct=0.5) is True
    assert detect_mean_shift([1, 1, 1], [1.1, 0.9], threshold_pct=0.5) is False
    assert detect_mean_shift([], [1]) is False
    assert detect_mean_shift([0, 0], [1], threshold_pct=0.1) is False


def test_should_trigger_retrain():
    assert should_trigger_retrain([0.9, 0.85, 0.8], drop_threshold=0.05) is True
    assert should_trigger_retrain([0.9, 0.89], drop_threshold=0.05) is False
    assert should_trigger_retrain([0.9], drift_flag=True) is True
    assert should_trigger_retrain([0, 0], drop_threshold=0.1) is False
    assert should_trigger_retrain([0.8], drop_threshold=0.1) is False
