"""Record processor — optimized implementation."""
from collections import Counter


def sum_squares(numbers):
    return sum(n * n for n in numbers)


def filter_evens(numbers):
    return [n for n in numbers if n % 2 == 0]


def find_duplicates(items):
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)
    return list(duplicates)


def word_counts(text):
    return dict(Counter(text.split()))
