"""Pipeline configuration constants and defaults."""

# Input/output settings
DEFAULT_DELIMITER = ","
DEFAULT_ENCODING = "utf-8"
MAX_LINE_LENGTH = 8192

# Data validation bounds
TEMPERATURE_MIN = -50.0
TEMPERATURE_MAX = 60.0
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0
PRESSURE_MIN = 870.0
PRESSURE_MAX = 1084.0

# Transformation settings
TEMPERATURE_PRECISION = 2
HUMIDITY_PRECISION = 1
PRESSURE_PRECISION = 1

# Output format
OUTPUT_DATE_FORMAT = "%Y-%m-%d"
OUTPUT_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Pipeline behavior
SKIP_INVALID_ROWS = True
STRICT_MODE = False
MAX_ERRORS_BEFORE_ABORT = 100
