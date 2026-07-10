"""Hidden tests for codebase understanding — module-level imports."""
import os
import sys
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

# Verify src/__init__.py exists (it should, from public test)
assert Path(workspace / "src" / "__init__.py").is_file()

# Verify all three modules can be imported independently
import src.config
assert hasattr(src.config, 'AppConfig')
assert hasattr(src.config, 'DatabaseConfig')
assert hasattr(src.config, 'RedisConfig')

import src.database
assert hasattr(src.database, 'Database')
assert hasattr(src.database, 'DatabasePool')

import src.cache
assert hasattr(src.cache, 'Cache')
assert hasattr(src.cache, 'CacheManager')

# Verify config property works with custom values
cfg = src.config.DatabaseConfig(host="remote", port=9999, name="proddb")
conn_str = cfg.connection_string
assert "remote" in conn_str
assert "9999" in conn_str
assert "proddb" in conn_str

# Verify DatabasePool max_connections is configurable
pool = src.database.DatabasePool(src.config.DatabaseConfig(), max_connections=4)
assert pool.max_connections == 4

print("ALL HIDDEN TESTS PASSED")
