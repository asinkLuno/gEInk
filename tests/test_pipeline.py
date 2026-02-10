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


def test_preprocess_skips_processed_files(test_images):
    """Verify preprocess skips _crop and _dithered files."""
    # Ensure we have some _crop and _dithered files
    crop_count = len(list(test_images.glob("*_crop.jpg")))
    dithered_count = len(list(test_images.glob("*_dithered.jpg")))

    if crop_count == 0 or dithered_count == 0:
        pytest.skip("Test requires existing _crop and _dithered files")

    # Count original files (non-processed)
    original_files = [
        f
        for f in test_images.iterdir()
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        and "_crop" not in f.name
        and "_dithered" not in f.name
    ]

    # Run preprocess again
    result = subprocess.run(
        ["geink", "preprocess", str(test_images)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Verify it only processed original files, not _crop or _dithered
    output_lines = result.stdout.strip().split("\n")
    processed_lines = [line for line in output_lines if "Processing" in line]

    assert len(processed_lines) == len(original_files), (
        f"Expected {len(original_files)} files to be processed, "
        f"but got {len(processed_lines)}"
    )
