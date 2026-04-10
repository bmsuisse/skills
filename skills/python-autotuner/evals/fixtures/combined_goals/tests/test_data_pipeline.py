"""Tests for data_pipeline.py."""
import json
from pathlib import Path

import pytest
from data_pipeline import filter_records, group_by_category, summarize, top_n_per_category


SAMPLE = [
    {"id": 1, "category": "A", "score": 80, "name": "Alice"},
    {"id": 2, "category": "B", "score": 60, "name": "Bob"},
    {"id": 3, "category": "A", "score": 90, "name": "Carol"},
    {"id": 4, "category": "B", "score": 40, "name": "Dan"},
    {"id": 5, "category": "A", "score": 70, "name": "Eve"},
    {"id": 6, "category": "C", "score": 55},   # no name field
]


def test_filter_score_range():
    result = filter_records(SAMPLE, min_score=65, max_score=95)
    assert len(result) == 3
    assert all(65 <= r["score"] <= 95 for r in result)


def test_filter_required_fields():
    result = filter_records(SAMPLE, required_fields=["name"])
    assert len(result) == 5
    assert all("name" in r for r in result)


def test_filter_no_criteria():
    result = filter_records(SAMPLE)
    assert len(result) == 6


def test_group_by_category():
    groups = group_by_category(SAMPLE)
    assert set(groups.keys()) == {"A", "B", "C"}
    assert len(groups["A"]) == 3
    assert len(groups["B"]) == 2


def test_top_n_per_category():
    groups = group_by_category(SAMPLE)
    top = top_n_per_category(groups, n=2)
    assert len(top["A"]) == 2
    # Top 2 in A should be Carol (90) and Alice (80)
    assert top["A"][0]["score"] >= top["A"][1]["score"]


def test_summarize_basic():
    result = summarize(SAMPLE)
    assert result["count"] == 6
    assert result["min"] == 40
    assert result["max"] == 90


def test_summarize_empty():
    result = summarize([])
    assert result == {"count": 0, "mean": 0, "min": 0, "max": 0}


def test_summarize_mean():
    records = [{"score": 10}, {"score": 20}, {"score": 30}]
    result = summarize(records)
    assert result["mean"] == 20.0


def test_top_n_benchmark(benchmark):
    import random
    big = [{"category": f"cat{i%10}", "score": random.randint(0,100)} for i in range(5000)]
    groups = group_by_category(big)
    result = benchmark(top_n_per_category, groups, 5)
    assert len(result) == 10


def test_filter_benchmark(benchmark):
    import random
    big = [{"score": random.randint(0, 100), "name": f"user{i}"} for i in range(5000)]
    result = benchmark(filter_records, big, 20, 80, ["name"])
    assert all(20 <= r["score"] <= 80 for r in result)
