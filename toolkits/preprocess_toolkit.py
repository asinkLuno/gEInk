from PIL import Image


def get_dominant_background_color(image_gray):
    """
    Estimates the dominant background color (black or white) of a grayscale image.
    This is a simple heuristic: it checks the average pixel value of the borders.
    """
    width, height = image_gray.size
    # Sample pixels from the borders
    border_pixels = []
    for x in range(width):
        border_pixels.append(image_gray.getpixel((x, 0)))  # Top border
        border_pixels.append(image_gray.getpixel((x, height - 1)))  # Bottom border
    for y in range(height):
        border_pixels.append(image_gray.getpixel((0, y)))  # Left border
        border_pixels.append(image_gray.getpixel((width - 1, y)))  # Right border

    if not border_pixels:
        return 255  # Default to white if no pixels sampled

    avg_color = sum(border_pixels) / len(border_pixels)
    return 0 if avg_color < 128 else 255  # Return 0 for black, 255 for white


def _preprocess_image(input_image_path, target_width, target_height):
    """
    Handles image preprocessing:
    1. Opens image and converts to grayscale.
    2. (Placeholder for Object Edge Detection & Cropping) - currently uses full image.
    3. Estimates dominant background color.
    4. Rotates image if portrait to fit landscape target dimensions.
    5. Pads and resizes the image to target_width x target_height while maintaining aspect ratio.

    Returns a PIL Image object.
    """
    try:
        img = Image.open(input_image_path).convert("L")  # Convert to grayscale
    except FileNotFoundError:
        print(f"Error: Input image '{input_image_path}' not found.")
        return None
    except Exception as e:
        print(f"Error opening or converting image '{input_image_path}': {e}")
        return None

    original_width, original_height = img.size
    print(
        f"Preprocessing '{input_image_path}' (Original: {original_width}x{original_height})"
    )

    # --- Step 2: Object Edge Detection & Cropping (Placeholder) ---
    # For a simple implementation, we'll assume the entire image is the object for now.
    # A more advanced version would use OpenCV for Canny edge detection,
    # finding contours, and then cropping to the bounding box of the main object.
    # For now, we'll just use the full image.
    cropped_img = img

    # Estimate dominant background color from the (uncropped) image borders
    bg_color = get_dominant_background_color(img)  # Use original image to get bg color

    # --- Step 3: Aspect Ratio Padding & Rotation ---
    cropped_width, cropped_height = cropped_img.size

    # Simpler approach: Always target 800x480. If the input image is "portrait" (height > width), rotate it.
    # This also handles the 5:3 / 3:5 ratio implicitly by fitting to 800x480.
    if original_height > original_width:
        # It's a portrait image, rotate it 90 degrees clockwise to become landscape
        img = img.rotate(90, expand=True)
        original_width, original_height = img.size  # Update dimensions after rotation
        print(
            f"Rotated image 90 degrees to fit landscape display. New dimensions: {original_width}x{original_height}"
        )

    # Now, fit the (potentially rotated) image into a canvas that will then be resized to 800x480
    scale_factor = min(target_width / original_width, target_height / original_height)
    resized_intermediate_width = int(original_width * scale_factor)
    resized_intermediate_height = int(original_height * scale_factor)

    resized_img = img.resize(
        (resized_intermediate_width, resized_intermediate_height), Image.LANCZOS
    )

    # Create a new image with target dimensions and background color
    padded_img = Image.new("L", (target_width, target_height), color=bg_color)
    # Paste the resized image onto the center of the padded canvas
    paste_x = (target_width - resized_intermediate_width) // 2
    paste_y = (target_height - resized_intermediate_height) // 2
    padded_img.paste(resized_img, (paste_x, paste_y))

    return padded_img
