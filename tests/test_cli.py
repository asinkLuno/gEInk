"""End-to-end tests for image processing CLI."""

import os
import subprocess

import pytest


class TestProcessImage:
    """End-to-end tests for image processing via subprocess."""

    def test_process_single_image(self, tmp_path, landscape_image):
        """Test processing a single landscape image."""
        output_path = str(tmp_path / "output.bin")
        result = subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('{landscape_image}', '{output_path}')",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert os.path.exists(output_path)

    def test_process_portrait_rotates(self, tmp_path, portrait_image):
        """Test that portrait images are rotated during processing."""
        output_path = str(tmp_path / "output.bin")
        result = subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('{portrait_image}', '{output_path}')",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert os.path.exists(output_path)

        file_size = os.path.getsize(output_path)
        expected_size = 800 * 480 // 8
        assert file_size == expected_size

    def test_process_nonexistent_file(self, tmp_path):
        """Test that processing non-existent file fails gracefully."""
        output_path = str(tmp_path / "output.bin")
        result = subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('/nonexistent/image.png', '{output_path}')",
            ],
            capture_output=True,
            text=True,
        )
        # Function returns False but doesn't raise exception, so returncode is 0
        assert result.returncode == 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()
        assert not os.path.exists(output_path)  # No file should be created

    def test_output_file_size(self, tmp_path, white_background_image):
        """Test that output file has correct size."""
        output_path = str(tmp_path / "output.bin")
        subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('{white_background_image}', '{output_path}')",
            ],
            capture_output=True,
            text=True,
        )
        assert os.path.exists(output_path)

        file_size = os.path.getsize(output_path)
        expected_size = 800 * 480 // 8
        assert file_size == expected_size

    def test_custom_dimensions(self, tmp_path, landscape_image):
        """Test processing with custom target dimensions."""
        output_path = str(tmp_path / "output.bin")
        result = subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('{landscape_image}', '{output_path}', 400, 300)",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert os.path.exists(output_path)

        file_size = os.path.getsize(output_path)
        expected_size = 400 * 300 // 8
        assert file_size == expected_size


@pytest.mark.test_img
class TestWithTestImages:
    """Tests using actual test images from test_img directory."""

    def test_process_test_image_1(self, tmp_path):
        """Process 图片_1.jpg from test_img directory."""
        test_image = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "test_img", "图片_1.jpg"
        )
        if not os.path.exists(test_image):
            pytest.skip("Test image not found")

        output_path = str(tmp_path / "图片_1.bin")
        result = subprocess.run(
            [
                "python",
                "-c",
                f"from image_processor import process_image; "
                f"process_image('{test_image}', '{output_path}')",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert os.path.exists(output_path)

        file_size = os.path.getsize(output_path)
        expected_size = 800 * 480 // 8
        assert file_size == expected_size

    def test_process_all_test_images(self, tmp_path):
        """Process all test images and verify outputs."""
        test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_img")
        if not os.path.exists(test_dir):
            pytest.skip("Test image directory not found")

        expected_files = [
            "图片_1.jpg",
            "图片_2.jpg",
            "图片_3.jpg",
            "图片_4.jpg",
            "图片_5.jpg",
        ]

        for filename in expected_files:
            test_image = os.path.join(test_dir, filename)
            if not os.path.exists(test_image):
                continue

            output_path = str(tmp_path / f"{filename}.bin")
            result = subprocess.run(
                [
                    "python",
                    "-c",
                    f"from image_processor import process_image; "
                    f"process_image('{test_image}', '{output_path}')",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"Failed to process {filename}: {result.stderr}"
            )
            assert os.path.exists(output_path)

            file_size = os.path.getsize(output_path)
            expected_size = 800 * 480 // 8
            assert file_size == expected_size, f"{filename} output size mismatch"
