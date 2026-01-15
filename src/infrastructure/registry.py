from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from application.features import FeatureExtractor
from application.model import IAnomalyDetector
from infrastructure.models.baseline import FrequencyBaselineDetector
from infrastructure.models.isolation_forest import IsolationForestDetector


class ModelRegistry:
    def __init__(self, artifact_dir: str) -> None:
        self.base_path = Path(artifact_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        detector: IAnomalyDetector,
        model_type: str,
        feature_extractor: FeatureExtractor,
        train_metrics: dict[str, float] | None = None,
    ) -> dict[str, object]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        model_dir = self.base_path / f"{model_type}_{timestamp}"
        detector.save(str(model_dir))
        metadata = {
            "model_type": model_type,
            "version": timestamp,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "feature_names": feature_extractor.feature_names,
            "train_metrics": train_metrics or {},
            "path": str(model_dir),
        }
        with open(model_dir / "metadata.json", "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=True, indent=2)
        with open(self.base_path / "latest.json", "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=True, indent=2)
        return metadata

    def load_latest(self) -> tuple[IAnomalyDetector, dict[str, object]]:
        latest_path = self.base_path / "latest.json"
        if not latest_path.exists():
            raise FileNotFoundError("No model artifacts found. Train a model first.")
        with open(latest_path, encoding="utf-8") as handle:
            metadata = json.load(handle)
        model_type = metadata.get("model_type")
        model_path = metadata.get("path")
        if not model_type or not model_path:
            raise ValueError("Invalid model metadata")
        detector = _load_detector(model_type, model_path)
        return detector, metadata


def _load_detector(model_type: str, path: str) -> IAnomalyDetector:
    model_type = model_type.lower()
    if model_type == "baseline":
        return FrequencyBaselineDetector.load(path)
    if model_type in {"isolation_forest", "iforest"}:
        return IsolationForestDetector.load(path)
    raise ValueError(f"Unsupported model type: {model_type}")
