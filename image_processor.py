import os

from toolkits import dithering_toolkit, preprocess_toolkit


def process_image(
    input_image_path,
    output_bin_path,
    target_width=800,
    target_height=480,
    dither_method="floyd_steinberg",
):
    """
    Processes an image for e-paper display:
    1. Preprocesses the image (grayscale, rotation, padding, resizing).
    2. Converts to 1-bit black and white using the specified dithering method.
    3. Saves as a raw binary file (.bin) for the e-paper display.
    """
    processed_img = preprocess_toolkit._preprocess_image(
        input_image_path, target_width, target_height
    )
    if processed_img is None:
        return False

    return dithering_toolkit.dither_and_convert_to_epd_format(
        processed_img, output_bin_path, target_width, target_height, dither_method
    )


if __name__ == "__main__":
    output_directory = "processed_images"
    os.makedirs(output_directory, exist_ok=True)

    # Example: Process images from the 'test_img' directory
    test_images_dir = "test_img"
    if os.path.exists(test_images_dir):
        for filename in os.listdir(test_images_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
                input_path = os.path.join(test_images_dir, filename)
                base_filename = os.path.splitext(filename)[0]

                # Process with Floyd-Steinberg (default)
                output_filename_fs = base_filename + "_fs.bin"
                output_path_fs = os.path.join(output_directory, output_filename_fs)
                print(f"Processing {filename} with Floyd-Steinberg...")
                process_image(
                    input_path, output_path_fs, dither_method="floyd_steinberg"
                )

                # Process with Jarvis, Judice, Ninke
                output_filename_jjn = base_filename + "_jjn.bin"
                output_path_jjn = os.path.join(output_directory, output_filename_jjn)
                print(f"Processing {filename} with Jarvis, Judice, Ninke...")
                process_image(
                    input_path, output_path_jjn, dither_method="jarvis_judice_ninke"
                )
    else:
        print(
            f"Directory '{test_images_dir}' not found. Please create it and add some images, or update the script with your image paths."
        )

    # You can also add individual calls like this:
    # process_image("my_picture.png", os.path.join(output_directory, "my_picture_fs.bin"), dither_method="floyd_steinberg")
    # process_image("my_picture.png", os.path.join(output_directory, "my_picture_jjn.bin"), dither_method="jarvis_judice_ninke")
