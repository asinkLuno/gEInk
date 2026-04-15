import math
import os
from typing import Callable, TypeVar

from dotenv import dotenv_values

# Load .env file values
config = dotenv_values(".env")

# Default values
DEFAULT_TARGET_WIDTH = 800
DEFAULT_TARGET_HEIGHT = 480
DEFAULT_COLOR_LEVELS = 2  # 1-bit (2 levels)

T = TypeVar("T")


def get_config_value(key: str, default: T, type_cast: Callable[[str], T]) -> T:
    """Get a configuration value, prioritizing environment variables."""
    # os.getenv returns Optional[str], config.get(key) returns Optional[str]
    raw_value = os.getenv(key) or config.get(key)
    if raw_value is None:
        return default
    try:
        return type_cast(str(raw_value))
    except (ValueError, TypeError):
        cast_name = getattr(type_cast, "__name__", str(type_cast))
        print(
            f"Warning: Could not cast '{raw_value}' for {key} to {cast_name}. Using default: {default}"
        )
        return default


TARGET_WIDTH = get_config_value("GEINK_TARGET_WIDTH", DEFAULT_TARGET_WIDTH, int)
TARGET_HEIGHT = get_config_value("GEINK_TARGET_HEIGHT", DEFAULT_TARGET_HEIGHT, int)
_color_levels = get_config_value("GEINK_COLOR_LEVELS", DEFAULT_COLOR_LEVELS, int)

# Validate COLOR_LEVELS
if not (2 <= _color_levels <= 256 and (_color_levels & (_color_levels - 1) == 0)):
    print(
        f"Error: GEINK_COLOR_LEVELS must be a power of 2 between 2 and 256. Found: {_color_levels}"
    )
    _color_levels = DEFAULT_COLOR_LEVELS
    print(f"Using default GEINK_COLOR_LEVELS: {_color_levels}")

COLOR_LEVELS: int = _color_levels

# Calculate bits per pixel
BITS_PER_PIXEL = int(math.log2(COLOR_LEVELS))

# Ensure these variables are accessible by other modules
__all__ = ["TARGET_WIDTH", "TARGET_HEIGHT", "COLOR_LEVELS", "BITS_PER_PIXEL"]
