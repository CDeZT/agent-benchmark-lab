"""Tests for codebase understanding.

These tests verify that the agent understood the codebase structure.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))


def test_config_classes_exist():
    """Verify configuration classes exist."""
    from src.config import AppConfig, DatabaseConfig, RedisConfig
    assert AppConfig is not None
    assert DatabaseConfig is not None
    assert RedisConfig is not None


def test_database_class_exists():
    """Verify database classes exist."""
    from src.database import Database, DatabasePool
    assert Database is not None
    assert DatabasePool is not None


def test_cache_class_exists():
    """Verify cache classes exist."""
    from src.cache import Cache, CacheManager
    assert Cache is not None
    assert CacheManager is not None


def test_config_has_connection_string():
    """Verify DatabaseConfig has connection_string property."""
    from src.config import DatabaseConfig
    config = DatabaseConfig(host="testhost", port=5432, name="testdb", user="testuser", password="testpass")
    assert hasattr(config, 'connection_string')
    assert "testhost" in config.connection_string


def test_database_connect_disconnect():
    """Verify Database can connect and disconnect."""
    from src.config import DatabaseConfig
    from src.database import Database

    config = DatabaseConfig()
    db = Database(config)
    assert db.connect() is True
    assert db.connected is True
    db.disconnect()
    assert db.connected is False


def test_cache_get_set():
    """Verify Cache can get and set values."""
    from src.config import RedisConfig
    from src.cache import Cache

    config = RedisConfig()
    cache = Cache(config)
    cache.connect()

    assert cache.set("key1", "value1") is True
    assert cache.get("key1") == "value1"
    assert cache.delete("key1") is True
    assert cache.get("key1") is None


def test_database_pool():
    """Verify DatabasePool manages connections."""
    from src.config import DatabaseConfig
    from src.database import DatabasePool

    config = DatabaseConfig()
    pool = DatabasePool(config, max_connections=2)

    conn1 = pool.get_connection()
    conn2 = pool.get_connection()

    assert len(pool.in_use) == 2

    pool.release_connection(conn1)
    assert len(pool.in_use) == 1
    assert len(pool.pool) == 1

    pool.close_all()
    assert len(pool.in_use) == 0
    assert len(pool.pool) == 0
