"""Cache module for handling caching operations."""

import json
import time
from typing import Any, Optional
from .config import RedisConfig


class Cache:
    """Cache manager using Redis."""

    def __init__(self, config: RedisConfig):
        """Initialize cache connection."""
        self.config = config
        self.connected = False
        self.storage = {}  # Simulated Redis storage

    def connect(self) -> bool:
        """Establish cache connection."""
        try:
            self.connected = True
            return True
        except Exception as e:
            print(f"Cache connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Close cache connection."""
        self.connected = False

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.connected:
            return None

        if key in self.storage:
            data, expiry = self.storage[key]
            if expiry and time.time() > expiry:
                del self.storage[key]
                return None
            return data

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        if not self.connected:
            return False

        expiry = time.time() + ttl if ttl else None
        self.storage[key] = (value, expiry)
        return True

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.connected:
            return False

        if key in self.storage:
            del self.storage[key]
            return True

        return False

    def clear(self) -> bool:
        """Clear all cache entries."""
        if not self.connected:
            return False

        self.storage.clear()
        return True

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.connected:
            return False

        return key in self.storage


class CacheManager:
    """Cache manager with multiple cache layers."""

    def __init__(self, config: RedisConfig):
        """Initialize cache manager."""
        self.config = config
        self.local_cache = {}
        self.redis_cache = Cache(config)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (local first, then Redis)."""
        # Try local cache first
        if key in self.local_cache:
            return self.local_cache[key]

        # Try Redis cache
        value = self.redis_cache.get(key)
        if value is not None:
            # Store in local cache
            self.local_cache[key] = value

        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        # Store in local cache
        self.local_cache[key] = value

        # Store in Redis cache
        return self.redis_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        # Remove from local cache
        if key in self.local_cache:
            del self.local_cache[key]

        # Remove from Redis cache
        return self.redis_cache.delete(key)

    def clear(self) -> bool:
        """Clear all cache entries."""
        self.local_cache.clear()
        return self.redis_cache.clear()
