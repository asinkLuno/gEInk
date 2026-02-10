"""Tests for dithering_toolkit module."""

import os

import pytest
from PIL import Image

from toolkits.dithering_toolkit import dither_and_convert_to_epd_format


class TestDitherAndConvert:
    """Tests for dithering algorithms and EPD format conversion."""

    def test_white_image_dithering_fs(self, tmp_path, output_bin_path):
        """Test Floyd-Steinberg dithering of solid white image."""
        img = Image.new("L", (800, 480), color=255)
        result = dither_and_convert_to_epd_format(
            img, output_bin_path, 800, 480, dither_method="floyd_steinberg"
        )
        assert result is True
        assert os.path.exists(output_bin_path)

        # Verify output file size (should be width * height / 8 bytes)
        file_size = os.path.getsize(output_bin_path)
        expected_size = 800 * 480 // 8
        assert file_size == expected_size

    def test_black_image_dithering_fs(self, tmp_path, output_bin_path):
        """Test Floyd-Steinberg dithering of solid black image."""
        img = Image.new("L", (800, 480), color=0)
        result = dither_and_convert_to_epd_format(
            img, output_bin_path, 800, 480, dither_method="floyd_steinberg"
        )
        assert result is True
        assert os.path.exists(output_bin_path)

    def test_grayscale_gradient_fs(self, tmp_path, output_bin_path):
        """Test Floyd-Steinberg dithering of grayscale gradient image."""
        # Create a horizontal gradient
        img = Image.new("L", (800, 480))
        for x in range(800):
            gray_value = int(255 * x / 800)
            for y in range(480):
                img.putpixel((x, y), gray_value)

        result = dither_and_convert_to_epd_format(
            img, output_bin_path, 800, 480, dither_method="floyd_steinberg"
        )
        assert result is True
        assert os.path.exists(output_bin_path)

    def test_bin_file_format_fs(self, tmp_path, output_bin_path):
        """Test that output is valid binary format for Floyd-Steinberg."""
        img = Image.new("L", (800, 480), color=128)
        result = dither_and_convert_to_epd_format(
            img, output_bin_path, 800, 480, dither_method="floyd_steinberg"
        )
        assert result is True

        # Read and verify binary content
        with open(output_bin_path, "rb") as f:
            content = f.read()

        assert len(content) == 800 * 480 // 8

    def test_dithering_produces_pattern_fs(self, tmp_path, output_bin_path):
        """Test that Floyd-Steinberg dithering produces different patterns than thresholding."""
        # Create a mid-gray image
        gray_img = Image.new("L", (800, 480), color=128)

        result = dither_and_convert_to_epd_format(
            gray_img, output_bin_path, 800, 480, dither_method="floyd_steinberg"
        )
        assert result is True

        # With dithering, we should see a mix of black and white pixels
        # not a solid color
        with open(output_bin_path, "rb") as f:
            content = f.read()

        # Should have some variation in bytes
        unique_bytes = set(content)
        assert len(unique_bytes) > 1, (
            "Floyd-Steinberg dithering should produce varied patterns"
        )

    def test_jarvis_judice_ninke_dithering_produces_pattern(
        self, tmp_path, output_bin_path
    ):
        """Test that Jarvis, Judice, Ninke dithering produces a varied pattern for a mid-gray image."""
        gray_img = Image.new("L", (800, 480), color=128)
        result = dither_and_convert_to_epd_format(
            gray_img, output_bin_path, 800, 480, dither_method="jarvis_judice_ninke"
        )
        assert result is True

        with open(output_bin_path, "rb") as f:
            content = f.read()

        unique_bytes = set(content)
        assert len(unique_bytes) > 1, (
            "Jarvis, Judice, Ninke dithering should produce varied patterns"
        )

    def test_invalid_dithering_method(self, tmp_path, output_bin_path):
        """Test that an invalid dithering method raises a ValueError."""
        img = Image.new("L", (800, 480), color=128)
        with pytest.raises(
            ValueError, match="Unsupported dithering method: invalid_method"
        ):
            dither_and_convert_to_epd_format(
                img, output_bin_path, 800, 480, dither_method="invalid_method"
            )

    def test_invalid_output_path(self, tmp_path):
        """Test handling of invalid output path."""
        img = Image.new("L", (800, 480), color=128)
        invalid_path = "/nonexistent/directory/output.bin"
        result = dither_and_convert_to_epd_format(img, invalid_path, 800, 480)
        assert result is False

    def test_partial_row_handling_fs(self, tmp_path, output_bin_path):
        """Test that width divisible by 8 works correctly with Floyd-Steinberg."""
        # 800 is divisible by 8 (100 bytes per row)
        output_bin_path = os.path.join(str(tmp_path), "test_partial.bin")

        img = Image.new("L", (800, 10), color=0)
        img.putpixel((799, 5), 255)  # Single white pixel in corner

        result = dither_and_convert_to_epd_format(
            img, output_bin_path, 800, 10, dither_method="floyd_steinberg"
        )
        assert result is True

        file_size = os.path.getsize(output_bin_path)
        expected_size = 800 * 10 // 8
        assert file_size == expected_size

    def test_small_image_dithering_fs(self, tmp_path):
        """Test Floyd-Steinberg dithering with smaller target dimensions."""
        output_path = str(tmp_path / "small.bin")
        img = Image.new("L", (400, 240), color=128)
        result = dither_and_convert_to_epd_format(
            img, output_path, 400, 240, dither_method="floyd_steinberg"
        )
        assert result is True

        file_size = os.path.getsize(output_path)
        expected_size = 400 * 240 // 8
        assert file_size == expected_size
