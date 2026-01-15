from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime

from domain.models import LogEvent

DEFAULT_PLAIN_PATTERNS = [
    (
        r'(?P<remote_addr>\S+) (?P<ident>\S+) (?P<remote_user>\S+) '
        r'\[(?P<time_local>[^\]]+)\] "(?P<request>[^"]*)" '
        r'(?P<status>\d{3}) (?P<bytes_sent>\S+) "(?P<referrer>[^"]*)" '
        r'"(?P<user_agent>[^"]*)"'
        r'(?: (?P<request_time>[\d.]+))?$'
    )
]

REQUEST_RE = re.compile(r"(?P<method>[A-Z]+)\s+(?P<path>\S+)(?:\s+(?P<protocol>HTTP/[0-9.]+))?")


class LogParser:
    def __init__(self, plain_patterns: Iterable[str] | None = None) -> None:
        patterns = list(plain_patterns) if plain_patterns else DEFAULT_PLAIN_PATTERNS
        self.plain_regexes = [re.compile(pattern) for pattern in patterns]

    def parse_json_line(self, line: str) -> LogEvent:
        payload = json.loads(line)
        normalized = _normalize_payload(payload)
        return LogEvent.model_validate(normalized)

    def parse_plain_text(self, line: str) -> LogEvent:
        for regex in self.plain_regexes:
            match = regex.match(line)
            if not match:
                continue
            data = match.groupdict()
            timestamp = _parse_nginx_time(data["time_local"])
            method, path, protocol = _parse_request_line(data.get("request"))
            status = _parse_int(data.get("status"))
            bytes_sent = _parse_int(data.get("bytes_sent"))
            request_time = _parse_float(data.get("request_time"))
            remote_user = _clean_dash(data.get("remote_user"))
            payload = {
                "timestamp": timestamp,
                "remote_addr": _clean_dash(data.get("remote_addr")),
                "remote_user": remote_user,
                "method": method,
                "path": path,
                "protocol": protocol,
                "status": status,
                "bytes_sent": bytes_sent,
                "referrer": _clean_dash(data.get("referrer")),
                "user_agent": _clean_dash(data.get("user_agent")),
                "request_time": request_time,
                "message": _build_message(method, path, protocol, data.get("request")),
                "level": _status_to_level(status),
                "service": "nginx",
            }
            return LogEvent.model_validate(payload)
        raise ValueError("Plain text log did not match nginx access log format")

    def parse_lines(self, lines: Iterable[str], fmt: str) -> list[LogEvent]:
        fmt = fmt.lower()
        events: list[LogEvent] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if fmt == "jsonl":
                events.append(self.parse_json_line(line))
            elif fmt == "plain":
                events.append(self.parse_plain_text(line))
            else:
                raise ValueError(f"Unsupported format: {fmt}")
        return events


def _normalize_payload(payload: dict) -> dict:
    data = dict(payload)
    if "timestamp" not in data:
        time_local = data.get("time_local") or data.get("@timestamp")
        if time_local:
            data["timestamp"] = _parse_nginx_time(str(time_local))
    request = data.get("request")
    method = data.get("method")
    path = data.get("path") or data.get("uri") or data.get("request_uri")
    protocol = data.get("protocol")
    if request and not method and not path:
        parsed_method, parsed_path, parsed_protocol = _parse_request_line(str(request))
        data.setdefault("method", parsed_method)
        data.setdefault("path", parsed_path)
        data.setdefault("protocol", parsed_protocol)
    method = data.get("method")
    path = data.get("path") or data.get("uri") or data.get("request_uri")
    protocol = data.get("protocol")
    status = data.get("status")
    if status is not None:
        data["status"] = _parse_int(status)
    bytes_sent = data.get("bytes_sent") or data.get("body_bytes_sent")
    if bytes_sent is not None:
        data["bytes_sent"] = _parse_int(bytes_sent)
    if "request_time" in data:
        data["request_time"] = _parse_float(data.get("request_time"))
    if not data.get("message"):
        data["message"] = _build_message(method, path, protocol, request)
    if not data.get("level"):
        data["level"] = _status_to_level(data.get("status"))
    data["remote_addr"] = _clean_dash(data.get("remote_addr") or data.get("ip"))
    data["remote_user"] = _clean_dash(data.get("remote_user") or data.get("user"))
    if not data.get("service") and not data.get("host"):
        data["service"] = "nginx"
    return data


def _parse_nginx_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        try:
            if value.endswith("Z"):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Unsupported timestamp format: {value}") from exc


def _parse_request_line(request: str | None) -> tuple[str | None, str | None, str | None]:
    if not request or request == "-":
        return None, None, None
    match = REQUEST_RE.match(request)
    if not match:
        return None, None, None
    return match.group("method"), match.group("path"), match.group("protocol")


def _build_message(
    method: str | None,
    path: str | None,
    protocol: str | None,
    request: str | None,
) -> str:
    if request and request != "-":
        return str(request)
    parts = [part for part in (method, path, protocol) if part]
    return " ".join(parts)


def _status_to_level(status: int | None) -> str:
    if status is None:
        return "INFO"
    if status >= 500:
        return "ERROR"
    if status >= 400:
        return "WARNING"
    if status >= 300:
        return "NOTICE"
    return "INFO"


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    if text == "-" or text == "":
        return None
    return int(float(text))


def _parse_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float):
        return value
    text = str(value)
    if text == "-" or text == "":
        return None
    return float(text)


def _clean_dash(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "-" or text == "":
        return None
    return text
