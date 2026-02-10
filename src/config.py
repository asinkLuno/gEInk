# config.py
import math
import os

from dotenv import dotenv_values

# Load .env file values
config = dotenv_values(".env")

# Default values
DEFAULT_TARGET_WIDTH = 800
DEFAULT_TARGET_HEIGHT = 480
DEFAULT_COLOR_LEVELS = 2  # 1-bit (2 levels)


def get_config_value(key, default, type_cast=str):
    """Get a configuration value, prioritizing environment variables."""
    value = os.getenv(key) or config.get(key)
    if value is None:
        return default
    try:
        return type_cast(value)
    except ValueError:
        print(
            f"Warning: Could not cast '{value}' for {key} to {type_cast.__name__}. Using default: {default}"
        )
        return default


TARGET_WIDTH = get_config_value("GEINK_TARGET_WIDTH", DEFAULT_TARGET_WIDTH, int)
TARGET_HEIGHT = get_config_value("GEINK_TARGET_HEIGHT", DEFAULT_TARGET_HEIGHT, int)
COLOR_LEVELS = get_config_value("GEINK_COLOR_LEVELS", DEFAULT_COLOR_LEVELS, int)

# Validate COLOR_LEVELS
if not (2 <= COLOR_LEVELS <= 256 and (COLOR_LEVELS & (COLOR_LEVELS - 1) == 0)):
    print(
        f"Error: GEINK_COLOR_LEVELS must be a power of 2 between 2 and 256. Found: {COLOR_LEVELS}"
    )
    COLOR_LEVELS = DEFAULT_COLOR_LEVELS
    print(f"Using default GEINK_COLOR_LEVELS: {COLOR_LEVELS}")

# Calculate bits per pixel
BITS_PER_PIXEL = int(math.log2(COLOR_LEVELS))

# Ensure these variables are accessible by other modules
__all__ = ["TARGET_WIDTH", "TARGET_HEIGHT", "COLOR_LEVELS", "BITS_PER_PIXEL"]
