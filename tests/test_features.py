from datetime import datetime, timezone

from application.features import FeatureExtractor
from domain.models import LogEvent


def test_feature_extraction_shape() -> None:
    event = LogEvent(
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        host="web-01",
        service="nginx",
        remote_addr="10.0.0.10",
        remote_user="alice",
        method="GET",
        path="/login",
        protocol="HTTP/1.1",
        status=200,
        bytes_sent=512,
        referrer="https://example.com/",
        user_agent="Mozilla/5.0",
        request_time=0.12,
        message="GET /login HTTP/1.1",
        level="INFO",
    )
    extractor = FeatureExtractor()
    features = extractor.transform([event])
    assert features.shape == (1, len(extractor.feature_names))
    assert features[0][0] >= 0
