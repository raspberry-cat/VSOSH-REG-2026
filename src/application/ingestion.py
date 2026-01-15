from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from application.parsers import LogParser
from domain.models import LogEvent


class LogIngestor:
    def __init__(self, parser: LogParser) -> None:
        self.parser = parser

    def ingest_file(self, path: Path, fmt: str) -> list[LogEvent]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return self.parser.parse_lines(lines, fmt)

    def ingest_stream(self, source: StreamSource) -> Iterable[LogEvent]:
        return source.read()


class StreamSource:
    def read(self) -> Iterable[LogEvent]:
        raise NotImplementedError("Implement stream reading for Kafka or Redis Streams")
