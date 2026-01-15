import pytest

from application.parsers import LogParser


def test_parse_json_line() -> None:
    parser = LogParser()
    line = (
        '{"timestamp":"2026-01-15T10:00:00+00:00","host":"web-01","remote_addr":"10.0.0.10",'
        '"method":"GET","path":"/login","protocol":"HTTP/1.1","status":200,"bytes_sent":512}'
    )
    event = parser.parse_json_line(line)
    assert event.host == "web-01"
    assert event.remote_addr == "10.0.0.10"
    assert event.method == "GET"
    assert event.level == "INFO"


def test_parse_plain_text() -> None:
    parser = LogParser()
    line = (
        '203.0.113.5 - alice [15/Jan/2026:10:00:00 +0000] "POST /api/v1/cart HTTP/1.1" '
        '404 1234 "-" "Mozilla/5.0" 0.231'
    )
    event = parser.parse_plain_text(line)
    assert event.remote_addr == "203.0.113.5"
    assert event.remote_user == "alice"
    assert event.method == "POST"
    assert event.status == 404
    assert event.level == "WARNING"


def test_parse_lines_unknown_format() -> None:
    parser = LogParser()
    with pytest.raises(ValueError):
        parser.parse_lines(["x"], "xml")
