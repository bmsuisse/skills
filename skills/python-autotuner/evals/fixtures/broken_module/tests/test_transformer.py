"""Tests for transformer.py."""
import pytest
from transformer import to_snake_case, truncate, count_words, reverse_words


def test_snake_case_camel():
    assert to_snake_case('CamelCase') == 'camel_case'


def test_snake_case_spaces():
    assert to_snake_case('hello world') == 'hello_world'


def test_snake_case_acronym():
    assert to_snake_case('HTTPSResponse') == 'https_response'


def test_truncate_no_op():
    assert truncate('short', 80) == 'short'


def test_truncate_cuts():
    result = truncate('a' * 100, 10, '...')
    assert len(result) == 10
    assert result.endswith('...')


def test_count_words_basic():
    result = count_words('hello world hello')
    assert result['hello'] == 2
    assert result['world'] == 1


def test_count_words_punctuation():
    result = count_words('hello, world!')
    assert 'hello' in result
    assert 'world' in result


def test_reverse_words():
    assert reverse_words('hello world foo') == 'foo world hello'


def test_reverse_single():
    assert reverse_words('hello') == 'hello'
