# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
#
# Purpose: Unit tests for the least-recently-used cache with expiry. A fake
# clock stands in for real time so the tests don't have to wait.

import pytest

from grazioso.services.cache import TTLCache


class FakeClock(object):
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_get_returns_stored_value():
    cache = TTLCache()
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert cache.hits == 1


def test_missing_key_returns_none():
    cache = TTLCache()
    assert cache.get("missing") is None
    assert cache.misses == 1


def test_least_recently_used_entry_is_evicted():
    cache = TTLCache(max_entries=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")          # a is now the most recently used
    cache.put("c", 3)       # so b is the one evicted
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_entries_expire():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=60, clock=clock)
    cache.put("a", 1)
    clock.now = 59
    assert cache.get("a") == 1
    clock.now = 61
    assert cache.get("a") is None
    assert len(cache) == 0


def test_get_or_compute_only_computes_once():
    cache = TTLCache()
    calls = []

    def compute():
        calls.append(1)
        return "result"

    assert cache.get_or_compute("key", compute) == "result"
    assert cache.get_or_compute("key", compute) == "result"
    assert len(calls) == 1


def test_get_or_compute_recomputes_after_expiry():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=10, clock=clock)
    values = iter(["old", "new"])
    cache.get_or_compute("key", lambda: next(values))
    clock.now = 11
    assert cache.get_or_compute("key", lambda: next(values)) == "new"


def test_clear():
    cache = TTLCache()
    cache.put("a", 1)
    cache.clear()
    assert len(cache) == 0


@pytest.mark.parametrize("kwargs", [{"max_entries": 0}, {"ttl_seconds": 0}])
def test_bad_settings_raise(kwargs):
    with pytest.raises(ValueError):
        TTLCache(**kwargs)
