from datetime import datetime, timezone

from application.features import FeatureExtractor
from domain.models import LogEvent
from infrastructure.models.baseline import FrequencyBaselineDetector
from infrastructure.models.isolation_forest import IsolationForestDetector


def _event(path: str, status: int = 200, method: str = "GET") -> LogEvent:
    return LogEvent(
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        host="web-01",
        service="nginx",
        remote_addr="10.0.0.10",
        method=method,
        path=path,
        protocol="HTTP/1.1",
        status=status,
        bytes_sent=512,
        message=f"{method} {path} HTTP/1.1",
        level="INFO",
    )


def test_baseline_scores_unseen_path_higher() -> None:
    detector = FrequencyBaselineDetector()
    normal = [_event("/index.html")]
    detector.train(normal)
    scores = detector.score(
        [_event("/index.html"), _event("/wp-admin", status=404)]
    )
    assert scores[1] > scores[0]


def test_isolation_forest_scores_between_zero_and_one() -> None:
    events = [
        _event("/"),
        _event("/api/v1/items", status=200),
        _event("/static/app.js", status=200),
        _event("/login", status=302),
        _event("/pricing", status=200),
    ]
    detector = IsolationForestDetector(feature_extractor=FeatureExtractor())
    detector.train(events)
    scores = detector.score(events)
    assert all(0.0 <= score <= 1.0 for score in scores)
