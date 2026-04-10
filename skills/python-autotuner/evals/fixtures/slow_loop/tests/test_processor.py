"""Tests for processor.py — used for both correctness and benchmarking."""
import pytest
from processor import sum_squares, filter_evens, find_duplicates, word_counts


def test_sum_squares():
    assert sum_squares([1, 2, 3, 4]) == 30
    assert sum_squares([]) == 0
    assert sum_squares([5]) == 25


def test_filter_evens():
    assert filter_evens([1, 2, 3, 4, 5, 6]) == [2, 4, 6]
    assert filter_evens([1, 3, 5]) == []


def test_find_duplicates():
    assert set(find_duplicates([1, 2, 2, 3, 3, 3])) == {2, 3}
    assert find_duplicates([1, 2, 3]) == []


def test_word_counts():
    result = word_counts("hello world hello")
    assert result == {"hello": 2, "world": 1}


def test_sum_squares_benchmark(benchmark):
    data = list(range(10_000))
    result = benchmark(sum_squares, data)
    assert result == sum(i * i for i in data)


def test_filter_evens_benchmark(benchmark):
    data = list(range(10_000))
    result = benchmark(filter_evens, data)
    assert len(result) == 5000


def test_find_duplicates_benchmark(benchmark):
    data = [i % 100 for i in range(1000)]
    result = benchmark(find_duplicates, data)
    assert len(result) == 99


def test_word_counts_benchmark(benchmark):
    text = " ".join(["word"] * 500 + ["other"] * 200 + ["thing"] * 100)
    result = benchmark(word_counts, text)
    assert result["word"] == 500
