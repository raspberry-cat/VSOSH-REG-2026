from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from application.features import FeatureExtractor
from domain.models import LogEvent
from infrastructure.models.baseline import FrequencyBaselineDetector
from infrastructure.models.isolation_forest import IsolationForestDetector
from infrastructure.registry import ModelRegistry


def train_model(
    events: Iterable[LogEvent],
    model_type: str,
    registry: ModelRegistry,
    feature_extractor: FeatureExtractor,
) -> dict[str, object]:
    events_list = list(events)
    model_type = model_type.lower()
    if model_type == "baseline":
        detector = FrequencyBaselineDetector(model_version="baseline")
    elif model_type in {"isolation_forest", "iforest"}:
        detector = IsolationForestDetector(
            feature_extractor=feature_extractor, model_version="iforest"
        )
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    detector.train(events_list)
    scores = detector.score(events_list)
    threshold, quantile = _calibrate_threshold(scores, model_type, detector)
    train_metrics = {
        "score_mean": float(np.mean(scores)) if scores else 0.0,
        "score_std": float(np.std(scores)) if scores else 0.0,
        "threshold": threshold,
        "threshold_quantile": quantile,
    }
    return registry.save(
        detector,
        model_type=model_type,
        feature_extractor=feature_extractor,
        train_metrics=train_metrics,
    )


def _calibrate_threshold(
    scores: list[float],
    model_type: str,
    detector: FrequencyBaselineDetector | IsolationForestDetector,
) -> tuple[float, float]:
    if not scores:
        return 0.0, 0.95
    if model_type == "baseline":
        quantile = 0.95
    else:
        quantile = 1.0 - float(detector.contamination)
    threshold = float(np.quantile(scores, quantile))
    return threshold, quantile
