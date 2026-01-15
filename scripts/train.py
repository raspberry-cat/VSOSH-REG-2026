#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from application.features import FeatureExtractor
from application.parsers import LogParser
from application.training import train_model
from infrastructure.registry import ModelRegistry
from infrastructure.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Train anomaly detection model")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", choices=["jsonl", "plain"], default="jsonl")
    parser.add_argument("--model", default=settings.model_type)
    args = parser.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines()
    parser_obj = LogParser()
    events = parser_obj.parse_lines(lines, args.format)

    registry = ModelRegistry(settings.artifact_dir)
    extractor = FeatureExtractor()
    metadata = train_model(events, args.model, registry, extractor)

    print(
        f"Saved model {metadata['model_type']} version {metadata['version']} to {metadata['path']}"
    )


if __name__ == "__main__":
    main()
