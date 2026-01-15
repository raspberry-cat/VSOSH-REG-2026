from __future__ import annotations

import re
from urllib.parse import urlparse

NUMBER_RE = re.compile(r"\b\d+\b")
PATH_HEX_RE = re.compile(r"\b[0-9a-fA-F]{6,}\b")
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def normalize_message(message: str) -> str:
    normalized = message
    normalized = IP_RE.sub("<IP>", normalized)
    normalized = UUID_RE.sub("<UUID>", normalized)
    normalized = HEX_RE.sub("<HEX>", normalized)
    normalized = NUMBER_RE.sub("<NUM>", normalized)
    return normalized


def normalize_path(path: str) -> str:
    clean = path.split("?", 1)[0]
    clean = PATH_HEX_RE.sub("<HEX>", clean)
    clean = NUMBER_RE.sub("<NUM>", clean)
    return clean


def path_extension(path: str) -> str:
    clean = path.split("?", 1)[0]
    if "." not in clean:
        return ""
    return "." + clean.rsplit(".", 1)[1].lower()


def referrer_domain(referrer: str | None) -> str:
    if not referrer or referrer == "-":
        return ""
    parsed = urlparse(referrer)
    return parsed.netloc or referrer
