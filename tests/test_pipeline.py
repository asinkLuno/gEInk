import subprocess
from pathlib import Path
from typing import Any

import pytest

TEST_IMG_DIR = Path("./test_img")


@pytest.fixture
def test_images(tmp_path: Any) -> Path:
    """Ensure test images exist."""
    if not TEST_IMG_DIR.exists():
        pytest.skip("test_img directory not found")
    return TEST_IMG_DIR


def test_process_pipeline(test_images: Path):
    """Full pipeline: process command on test images."""
    # Clean up previous output files
    for f in test_images.glob("*.bin"):
        f.unlink()
    for f in test_images.glob("*_preview.png"):
        f.unlink()

    # Run process
    result = subprocess.run(
        ["uv", "run", "geink", "process", str(test_images)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"process failed: {result.stderr}"

    # Check .bin files generated
    bin_files = list(test_images.glob("*.bin"))
    assert len(bin_files) > 0, "No .bin files generated"

    # Check _preview files generated
    preview_files = list(test_images.glob("*_preview.png"))
    assert len(preview_files) > 0, "No _preview files generated"


def test_gridcut(test_images: Path):
    """Verify gridcut command."""
    test_img = test_images / "test.jpg"
    if not test_img.exists():
        pytest.skip("test image not found")

    result = subprocess.run(
        ["uv", "run", "geink", "gridcut", str(test_img), "--rows", "2", "--cols", "2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"gridcut failed: {result.stderr}"

    output_dir = test_images / "test"
    assert output_dir.exists(), "Gridcut output directory not found"
    tiles = list(output_dir.glob("*.jpg"))
    # The dummy image might have been renamed or used a different suffix
    # Let's check for any image suffix
    tiles = [
        f for f in output_dir.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]
    assert len(tiles) == 4, f"Expected 4 tiles, found {len(tiles)}"


@pytest.mark.test_img
def test_ascii_art(test_images: Path):
    """Verify ascii-art command produces output."""
    test_img = test_images / "test.jpg"
    if not test_img.exists():
        pytest.skip("test image not found")

    result = subprocess.run(
        ["uv", "run", "geink", "ascii-art", str(test_img)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"ascii-art failed: {result.stderr}"

    out_file = test_images / "test_ascii.png"
    assert out_file.exists(), "ASCII art output file not found"


@pytest.mark.test_img
def test_pointillize(test_images: Path):
    """Verify pointillize command."""
    test_img = test_images / "test.jpg"
    if not test_img.exists():
        pytest.skip("test image not found")

    result = subprocess.run(
        ["uv", "run", "geink", "pointillize", str(test_img)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"pointillize failed: {result.stderr}"

    out_file = test_images / "test_pointillism.png"
    assert out_file.exists(), "Pointillism output file not found"
