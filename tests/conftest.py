"""Test fixtures for e-ink image processor tests."""

import os

import pytest
from PIL import Image

# Test image directory
TEST_IMG_DIR = os.path.join(os.path.dirname(__file__), "test_img")


@pytest.fixture
def white_background_image(tmp_path):
    """Create a test image with white background."""
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    # Add a black rectangle in the center
    for x in range(150, 250):
        for y in range(100, 200):
            img.putpixel((x, y), (0, 0, 0))
    path = tmp_path / "white_bg.png"
    img.save(path)
    return str(path)


@pytest.fixture
def black_background_image(tmp_path):
    """Create a test image with black background."""
    img = Image.new("RGB", (400, 300), color=(0, 0, 0))
    # Add a white rectangle in the center
    for x in range(150, 250):
        for y in range(100, 200):
            img.putpixel((x, y), (255, 255, 255))
    path = tmp_path / "black_bg.png"
    img.save(path)
    return str(path)


@pytest.fixture
def portrait_image(tmp_path):
    """Create a portrait-oriented test image (height > width)."""
    img = Image.new("RGB", (300, 400), color=(200, 200, 200))
    path = tmp_path / "portrait.png"
    img.save(path)
    return str(path)


@pytest.fixture
def landscape_image(tmp_path):
    """Create a landscape-oriented test image (width > height)."""
    img = Image.new("RGB", (600, 400), color=(150, 150, 150))
    path = tmp_path / "landscape.png"
    img.save(path)
    return str(path)


@pytest.fixture
def small_image(tmp_path):
    """Create a small test image that needs upscaling."""
    img = Image.new("RGB", (100, 80), color=(100, 100, 100))
    path = tmp_path / "small.png"
    img.save(path)
    return str(path)


@pytest.fixture
def large_image(tmp_path):
    """Create a large test image that needs downscaling."""
    img = Image.new("RGB", (1600, 1200), color=(180, 180, 180))
    path = tmp_path / "large.png"
    img.save(path)
    return str(path)


@pytest.fixture
def grayscale_image(tmp_path):
    """Create a grayscale test image."""
    img = Image.new("L", (500, 400), color=128)
    path = tmp_path / "grayscale.png"
    img.save(path)
    return str(path)


@pytest.fixture
def output_bin_path(tmp_path):
    """Provide a path for output .bin file."""
    return str(tmp_path / "output.bin")
