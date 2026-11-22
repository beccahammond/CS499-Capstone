# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
#
# Purpose: A small least-recently-used cache with an expiry time. The
# original dashboard queried MongoDB again every time anyone clicked a filter,
# even if they had clicked the same one seconds earlier.
#
# Data structure: an OrderedDict keeps keys in the order they were last used.
#   get:  dictionary lookup, then move_to_end to mark it as recently used. O(1)
#   put:  insert at the end, then pop the oldest entry if over capacity. O(1)
# Python's functools.lru_cache can't expire entries, and stale data is the
# trade-off with caching, so this version also drops anything older than
# ttl_seconds.

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Hashable, Optional

DEFAULT_MAX_ENTRIES = 64
DEFAULT_TTL_SECONDS = 60


class TTLCache(object):
    """ Least-recently-used cache where entries also expire after ttl_seconds """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES,
                 ttl_seconds: float = DEFAULT_TTL_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        # clock can be swapped out in the tests to fake the passing of time
        self._clock = clock
        self._entries: "OrderedDict[Hashable, tuple]" = OrderedDict()
        # Dash can run callbacks on more than one thread, so changes to the
        # OrderedDict are made one at a time
        self._lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Optional[Any]:
        """ Return the cached value, or None if it is missing or expired. O(1). """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            stored_at, value = entry
            if self._clock() - stored_at > self.ttl_seconds:
                del self._entries[key]
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: Hashable, value: Any) -> None:
        """ Store a value, evicting the least recently used entry if full. O(1). """
        with self._lock:
            self._entries[key] = (self._clock(), value)
            self._entries.move_to_end(key)
            if len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def get_or_compute(self, key: Hashable, compute: Callable[[], Any]) -> Any:
        """ Return the cached value, or call compute() and cache what it returns """
        value = self.get(key)
        if value is None:
            value = compute()
            self.put(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
