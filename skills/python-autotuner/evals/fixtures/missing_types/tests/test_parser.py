"""Tests for parser.py."""
import pytest
from parser import detect_delimiter, parse_header, parse_row, parse_csv, summarize


def test_detect_delimiter_comma():
    assert detect_delimiter("a,b,c") == ","


def test_detect_delimiter_tab():
    assert detect_delimiter("a\tb\tc") == "\t"


def test_detect_delimiter_fallback():
    assert detect_delimiter("abc") == ","


def test_parse_header():
    assert parse_header("First Name,Last Name,Age", ",") == ["first_name", "last_name", "age"]


def test_parse_row_ok():
    result = parse_row("Alice,Smith,30", ",", ["first_name", "last_name", "age"])
    assert result == {"first_name": "Alice", "last_name": "Smith", "age": "30"}


def test_parse_row_wrong_cols():
    result = parse_row("Alice,Smith", ",", ["first_name", "last_name", "age"])
    assert result is None


def test_parse_csv_basic():
    text = "name,age\nAlice,30\nBob,25"
    result = parse_csv(text)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"


def test_parse_csv_empty():
    assert parse_csv("") == []


def test_parse_csv_error_raises():
    text = "name,age\nAlice"
    with pytest.raises(ValueError):
        parse_csv(text)


def test_parse_csv_skip_errors():
    text = "name,age\nAlice\nBob,25"
    result = parse_csv(text, skip_errors=True)
    assert len(result) == 1
    assert result[0]["name"] == "Bob"


def test_summarize():
    records = [{"val": "10"}, {"val": "20"}, {"val": "30"}]
    result = summarize(records, ["val"])
    assert result["val"]["min"] == 10.0
    assert result["val"]["max"] == 30.0
    assert result["val"]["avg"] == 20.0
