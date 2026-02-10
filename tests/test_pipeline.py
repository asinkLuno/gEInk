import subprocess
from pathlib import Path

import pytest

TEST_IMG_DIR = Path("./test_img")


@pytest.fixture
def test_images(tmp_path):
    """Ensure test images exist."""
    if not TEST_IMG_DIR.exists():
        pytest.skip("test_img directory not found")
    return TEST_IMG_DIR


def test_preprocess_and_dither(test_images):
    """Full pipeline: preprocess then dither on test images."""
    # Clean up previous output files
    for f in test_images.glob("*_crop.jpg"):
        f.unlink()
    for f in test_images.glob("*_dithered.jpg"):
        f.unlink()

    # Run preprocess
    result = subprocess.run(
        ["geink", "preprocess", str(test_images)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"preprocess failed: {result.stderr}"

    # Check _crop files generated
    crop_files = list(test_images.glob("*_crop.jpg"))
    assert len(crop_files) > 0, "No _crop files generated"

    # Run dither
    result = subprocess.run(
        ["geink", "dither", str(test_images)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"dither failed: {result.stderr}"

    # Check _dithered files generated
    dithered_files = list(test_images.glob("*_dithered.jpg"))
    assert len(dithered_files) > 0, "No _dithered files generated"
