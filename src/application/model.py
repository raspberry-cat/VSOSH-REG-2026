from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import AnomalyResult, LogEvent


class IAnomalyDetector(ABC):
    @abstractmethod
    def train(self, events: list[LogEvent]) -> None:
        raise NotImplementedError

    @abstractmethod
    def score(self, events: list[LogEvent]) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def predict(self, events: list[LogEvent], threshold: float) -> list[AnomalyResult]:
        raise NotImplementedError

    @abstractmethod
    def save(self, path: str) -> None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(cls, path: str):
        raise NotImplementedError
