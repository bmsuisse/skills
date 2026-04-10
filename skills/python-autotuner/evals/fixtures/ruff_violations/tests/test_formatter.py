"""Tests for formatter.py."""
from formatter import format_name, build_report, is_valid_email


def test_format_name_no_middle():
    assert format_name("John", "Doe") == "John Doe"


def test_format_name_with_middle():
    assert format_name("John", "Doe", "William") == "John William Doe"


def test_build_report():
    data = [{"key": "value"}]
    result = build_report(data, "Test")
    assert "Test" in result
    assert "key: value" in result


def test_is_valid_email():
    assert is_valid_email("user@example.com") is True
    assert is_valid_email("not-an-email") is False
