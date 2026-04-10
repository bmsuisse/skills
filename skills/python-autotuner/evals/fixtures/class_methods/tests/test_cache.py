"""Tests for cache.py."""
import pytest
from cache import SimpleCache


@pytest.fixture()
def cache():
    return SimpleCache(max_size=3)


def test_get_miss(cache):
    assert cache.get("missing") is None


def test_set_and_get(cache):
    cache.set("a", 1)
    assert cache.get("a") == 1


def test_set_overwrites(cache):
    cache.set("a", 1)
    cache.set("a", 2)
    assert cache.get("a") == 2
    assert cache.size() == 1


def test_eviction(cache):
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)   # should evict "a"
    assert cache.get("a") is None
    assert cache.get("d") == 4
    assert cache.size() == 3


def test_delete(cache):
    cache.set("a", 1)
    cache.delete("a")
    assert cache.get("a") is None
    assert cache.size() == 0


def test_delete_missing(cache):
    cache.delete("nonexistent")   # must not raise


def test_has(cache):
    cache.set("x", 42)
    assert cache.has("x") is True
    assert cache.has("y") is False


def test_keys_values(cache):
    cache.set("a", 1)
    cache.set("b", 2)
    assert set(cache.keys()) == {"a", "b"}
    assert set(cache.values()) == {1, 2}


def test_get_or_set(cache):
    called = []
    def make_value():
        called.append(1)
        return 99
    v1 = cache.get_or_set("k", make_value)
    v2 = cache.get_or_set("k", make_value)
    assert v1 == v2 == 99
    assert len(called) == 1   # default_fn called only once


def test_update_many_dict(cache):
    cache.update_many({"a": 1, "b": 2})
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_update_many_list(cache):
    cache.update_many([("x", 10), ("y", 20)])
    assert cache.get("x") == 10


def test_clear(cache):
    cache.set("a", 1)
    cache.clear()
    assert cache.size() == 0


def test_get_benchmark(benchmark):
    c = SimpleCache(max_size=1000)
    for i in range(1000):
        c.set(f"key{i}", i)
    result = benchmark(c.get, "key500")
    assert result == 500


def test_set_benchmark(benchmark):
    c = SimpleCache(max_size=500)
    keys = [f"key{i}" for i in range(200)]
    def do_sets():
        for k in keys:
            c.set(k, 42)
    benchmark(do_sets)
