"""Simple LRU-style cache class — slow methods, missing types, high complexity."""


class SimpleCache:
    """A naive cache without any eviction or type hints."""

    def __init__(self, max_size):
        self.max_size = max_size
        self.store = []   # list of (key, value) tuples — O(n) lookup

    def get(self, key):
        """Get a value by key. Returns None if not found."""
        for i in range(len(self.store)):
            if self.store[i][0] == key:
                return self.store[i][1]
        return None

    def set(self, key, value):
        """Set a key-value pair, evicting oldest if over max_size."""
        # Check if key already exists — O(n) scan
        found = False
        for i in range(len(self.store)):
            if self.store[i][0] == key:
                self.store[i] = (key, value)
                found = True
                break
        if not found:
            if len(self.store) >= self.max_size:
                # Evict first item (oldest)
                self.store = self.store[1:]
            self.store.append((key, value))

    def delete(self, key):
        """Remove a key from the cache."""
        new_store = []
        for item in self.store:
            if item[0] != key:
                new_store.append(item)
        self.store = new_store

    def has(self, key):
        """Check if a key exists."""
        for item in self.store:
            if item[0] == key:
                return True
        return False

    def keys(self):
        """Return all keys."""
        result = []
        for item in self.store:
            result.append(item[0])
        return result

    def values(self):
        """Return all values."""
        result = []
        for item in self.store:
            result.append(item[1])
        return result

    def size(self):
        """Return number of cached items."""
        return len(self.store)

    def clear(self):
        """Remove all items."""
        self.store = []

    def get_or_set(self, key, default_fn):
        """Return cached value, or call default_fn(), cache and return its result."""
        # O(n) has() then O(n) get() = 2× unnecessary scans
        if self.has(key):
            return self.get(key)
        else:
            value = default_fn()
            self.set(key, value)
            return value

    def update_many(self, items):
        """Set multiple key-value pairs from a dict or list of tuples."""
        if type(items) == dict:
            for k in items.keys():
                self.set(k, items[k])
        elif type(items) == list:
            for item in items:
                self.set(item[0], item[1])
        else:
            raise ValueError("items must be a dict or list of tuples")
