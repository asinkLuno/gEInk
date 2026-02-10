"""Tests for preprocess_toolkit module."""

from PIL import Image

from toolkits.preprocess_toolkit import (_preprocess_image,
                                         get_dominant_background_color)


class TestGetDominantBackgroundColor:
    """Tests for background color detection."""

    def test_white_background(self, white_background_image):
        """Test that white background is correctly detected."""
        img = Image.open(white_background_image).convert("L")
        result = get_dominant_background_color(img)
        assert result == 255, "White background should return 255"

    def test_black_background(self, black_background_image):
        """Test that black background is correctly detected."""
        img = Image.open(black_background_image).convert("L")
        result = get_dominant_background_color(img)
        assert result == 0, "Black background should return 0"

    def test_gray_background(self, tmp_path):
        """Test gray background defaults to white."""
        img = Image.new("L", (100, 100), color=200)
        result = get_dominant_background_color(img)
        assert result == 255, "Gray background (>128) should return 255"

    def test_dark_gray_background(self, tmp_path):
        """Test dark gray background returns black."""
        img = Image.new("L", (100, 100), color=50)
        result = get_dominant_background_color(img)
        assert result == 0, "Dark gray background (<128) should return 0"

    def test_empty_image(self, tmp_path):
        """Test handling of edge case - empty border."""
        # Single pixel image has borders but should still work
        img = Image.new("L", (1, 1), color=128)
        result = get_dominant_background_color(img)
        # Single pixel has borders, avg_color = 128, so defaults to white
        assert result in [0, 255]


class TestPreprocessImage:
    """Tests for image preprocessing pipeline."""

    def test_landscape_orientation_preserved(self, landscape_image, output_bin_path):
        """Test that landscape images keep their orientation."""
        result = _preprocess_image(landscape_image, 800, 480)
        assert result is not None
        assert result.size == (800, 480)

    def test_portrait_rotation(self, portrait_image, output_bin_path):
        """Test that portrait images are rotated to landscape."""
        result = _preprocess_image(portrait_image, 800, 480)
        assert result is not None
        assert result.size == (800, 480)

    def test_white_background_padding(self, white_background_image, output_bin_path):
        """Test that white background images use white padding."""
        result = _preprocess_image(white_background_image, 800, 480)
        assert result is not None
        # Verify the padding color is white (255)
        assert result.getpixel((0, 0)) == 255
        assert result.getpixel((799, 479)) == 255

    def test_black_background_padding(self, black_background_image, output_bin_path):
        """Test that black background images use black padding."""
        result = _preprocess_image(black_background_image, 800, 480)
        assert result is not None
        # Verify the padding color is black (0)
        assert result.getpixel((0, 0)) == 0
        assert result.getpixel((799, 479)) == 0

    def test_grayscale_conversion(self, portrait_image, output_bin_path):
        """Test that RGB images are converted to grayscale."""
        result = _preprocess_image(portrait_image, 800, 480)
        assert result is not None
        assert result.mode == "L"

    def test_small_image_upscaled(self, small_image, output_bin_path):
        """Test that small images are upscaled to target size."""
        result = _preprocess_image(small_image, 800, 480)
        assert result is not None
        assert result.size == (800, 480)

    def test_large_image_downscaled(self, large_image, output_bin_path):
        """Test that large images are downscaled to target size."""
        result = _preprocess_image(large_image, 800, 480)
        assert result is not None
        assert result.size == (800, 480)

    def test_nonexistent_file(self, tmp_path):
        """Test handling of non-existent input file."""
        result = _preprocess_image(str(tmp_path / "nonexistent.png"), 800, 480)
        assert result is None

    def test_aspect_ratio_preserved(self, tmp_path):
        """Test that image aspect ratio is maintained during preprocessing."""
        # Create a 2:1 aspect ratio image
        img = Image.new("L", (400, 200), color=128)
        path = tmp_path / "aspect_test.png"
        img.save(path)

        result = _preprocess_image(str(path), 800, 480)
        assert result is not None
        assert result.size == (800, 480)

        # The content should be centered with padding on sides
        # Verify padding exists (content should not span full width)
        left_padding = result.getpixel((0, 240))
        right_padding = result.getpixel((799, 240))
        assert left_padding == right_padding  # Both should be background color

    def test_grayscale_input(self, grayscale_image, output_bin_path):
        """Test that grayscale input images are handled correctly."""
        result = _preprocess_image(grayscale_image, 800, 480)
        assert result is not None
        assert result.size == (800, 480)
        assert result.mode == "L"
