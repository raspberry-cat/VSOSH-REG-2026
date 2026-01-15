from domain.normalization import (
    normalize_message,
    normalize_path,
    path_extension,
    referrer_domain,
)


def test_normalize_path_strips_query_and_masks_tokens() -> None:
    path = "/api/v1/items/123?debug=1"
    assert normalize_path(path) == "/api/v1/items/<NUM>"


def test_normalize_message_masks_identifiers() -> None:
    message = (
        "GET /item/42 from 192.168.1.10 id=0xdeadbeef "
        "user=550e8400-e29b-41d4-a716-446655440000"
    )
    normalized = normalize_message(message)
    assert "<IP>" in normalized
    assert "<UUID>" in normalized
    assert "<HEX>" in normalized
    assert "<NUM>" in normalized


def test_path_extension_handles_query() -> None:
    assert path_extension("/static/app.js?v=1") == ".js"
    assert path_extension("/login") == ""


def test_referrer_domain_parses_host() -> None:
    assert referrer_domain("https://example.com/path") == "example.com"
    assert referrer_domain("-") == ""
