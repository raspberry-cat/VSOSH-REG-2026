#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest logs via API")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--format", choices=["jsonl", "plain"], default="jsonl")
    parser.add_argument("--url", default="http://localhost:8000/ingest")
    args = parser.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines()
    payload = {"format": args.format, "lines": lines}
    data = json.dumps(payload).encode("utf-8")
    request = Request(args.url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        print(body)


if __name__ == "__main__":
    main()
