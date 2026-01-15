from __future__ import annotations

import logging

from application.features import FeatureExtractor
from application.parsers import LogParser
from domain.models import AnomalyResult
from infrastructure.registry import ModelRegistry
from infrastructure.settings import Settings
from infrastructure.storage import Storage

logger = logging.getLogger(__name__)


class AnomalyService:
    def __init__(
        self,
        settings: Settings,
        parser: LogParser,
        feature_extractor: FeatureExtractor,
        registry: ModelRegistry,
        storage: Storage,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.feature_extractor = feature_extractor
        self.registry = registry
        self.storage = storage
        self.detector, self.metadata = self.registry.load_latest()

    @property
    def threshold(self) -> float:
        train_metrics = self.metadata.get("train_metrics") or {}
        calibrated = train_metrics.get("threshold")
        if isinstance(calibrated, (int, float)):
            return float(calibrated)
        model_type = self.metadata.get("model_type", "")
        if model_type == "baseline":
            return self.settings.baseline_threshold
        return self.settings.anomaly_threshold

    def ingest(self, lines: list[str], fmt: str) -> list[AnomalyResult]:
        events = self.parser.parse_lines(lines, fmt)
        results = self.detector.predict(events, self.threshold)
        self.storage.save_results(results)
        logger.info("ingested_logs", extra={"count": len(results)})
        return results

    def get_anomalies(self, limit: int = 50, min_score: float | None = None) -> list[dict]:
        return self.storage.get_anomalies(limit=limit, min_score=min_score)

    def get_metrics(self) -> dict:
        return self.storage.metrics()
