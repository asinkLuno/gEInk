#!/usr/bin/env python3
"""
Upload binary image data to ESP8266 e-paper display.

Converts a .bin file (800x480 monochrome, 1-bit per pixel) to the encoded
format expected by the SimpleLoader server and sends it via HTTP POST.

Usage:
  python upload_to_epd.py --bin image.bin --host 192.168.10.211
"""

import argparse
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Install with: pip install requests")
    sys.exit(1)

# Constants for 800x480 display
TARGET_WIDTH = 800
TARGET_HEIGHT = 480
BYTES_PER_PIXEL = 1 / 8  # 1 bit per pixel, 8 pixels per byte
TOTAL_BYTES = TARGET_WIDTH * TARGET_HEIGHT // 8  # 48000 bytes


def encode_byte(b: int) -> str:
    """
    Encode a single byte (0-255) into two characters 'a' to 'p' (0-15).
    Each nibble (4 bits) becomes a character: 'a'=0, 'b'=1, ..., 'p'=15.
    """
    low = b & 0x0F
    high = (b >> 4) & 0x0F
    return chr(ord("a") + low) + chr(ord("a") + high)


def encode_data(data: bytes) -> str:
    """Encode binary data into string format expected by ESP8266."""
    return "".join(encode_byte(b) for b in data)


def upload_chunk(host: str, chunk: str, chunk_size: int) -> bool:
    """
    Upload a single chunk of encoded data to the ESP8266.
    The chunk must already include the 4-byte length and "LOAD" suffix.
    """
    url = f"http://{host}/upload"
    try:
        response = requests.post(url, data={"data": chunk}, timeout=30)
        if response.status_code == 200:
            print(f"  Uploaded {chunk_size} bytes: {response.text.strip()}")
            return True
        else:
            print(f"  Error: {response.status_code} - {response.text.strip()}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  Network error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Upload binary image to ESP8266 e-paper"
    )
    parser.add_argument("--bin", "-b", required=True, help="Path to .bin file")
    parser.add_argument("--host", "-H", required=True, help="ESP8266 IP address")
    parser.add_argument(
        "--chunk-size",
        "-c",
        type=int,
        default=1400,
        help="Maximum chunk size in characters (default: 1400)",
    )
    args = parser.parse_args()

    bin_path = Path(args.bin)
    if not bin_path.exists():
        print(f"Error: File not found: {bin_path}")
        return 1

    # Read binary file
    with open(bin_path, "rb") as f:
        data = f.read()

    # Verify file size
    if len(data) != TOTAL_BYTES:
        print(f"Warning: Expected {TOTAL_BYTES} bytes, got {len(data)} bytes")
        print("Make sure the image is 800x480 monochrome (1-bit per pixel)")
        proceed = input("Continue anyway? (y/N): ").lower().strip()
        if proceed != "y":
            return 1

    print(f"Loaded {len(data)} bytes from {bin_path.name}")

    # Encode entire data
    print("Encoding data...")
    encoded = encode_data(data)
    total_chars = len(encoded)
    print(f"Encoded to {total_chars} characters ({total_chars / 2} bytes equivalent)")

    # Initialize display
    init_url = f"http://{args.host}/init"
    try:
        print("Initializing display...")
        response = requests.get(init_url, timeout=10)
        if response.status_code == 200:
            print(f"Init: {response.text.strip()}")
        else:
            print(f"Init failed: {response.status_code} - {response.text.strip()}")
            return 1
    except requests.exceptions.RequestException as e:
        print(f"Init error: {e}")
        return 1

    # Split into chunks (each chunk will have 4-byte length + "LOAD" appended)
    # We'll send chunks of approximately args.chunk_size characters (excluding suffix)
    # Each chunk must be a multiple of 2 characters (since 2 chars per byte)
    chunk_chars = (args.chunk_size // 2) * 2  # ensure even number
    if chunk_chars <= 8:
        print(f"Chunk size too small: {chunk_chars}")
        return 1

    chunks = []
    pos = 0
    while pos < total_chars:
        # Calculate chunk size (leave room for 4-byte length + "LOAD")
        remaining = total_chars - pos
        chunk_size = min(chunk_chars - 8, remaining)  # reserve 8 chars for length+LOAD
        if chunk_size <= 0:
            chunk_size = remaining

        # Ensure chunk_size is even
        if chunk_size % 2 != 0:
            chunk_size -= 1
            if chunk_size <= 0:
                break

        chunk = encoded[pos : pos + chunk_size]
        chunks.append(chunk)
        pos += chunk_size

    print(f"Splitting into {len(chunks)} chunks...")

    # Upload each chunk
    success_count = 0
    for i, chunk in enumerate(chunks, 1):
        # Add 4-byte length (encoded as 4 characters) and "LOAD"
        # Length is the number of characters in the data portion (chunk)
        length_chars = len(chunk)
        # Encode length_chars as 4 characters (16-bit value, little-endian)
        # Each character represents 4 bits, so we need to split into nibbles
        # First character: bits 0-3, second: bits 4-7, third: bits 8-11, fourth: bits 12-15
        len_chars = (
            chr(ord("a") + (length_chars & 0x0F))
            + chr(ord("a") + ((length_chars >> 4) & 0x0F))
            + chr(ord("a") + ((length_chars >> 8) & 0x0F))
            + chr(ord("a") + ((length_chars >> 12) & 0x0F))
        )
        full_chunk = chunk + len_chars + "LOAD"

        bytes_count = length_chars // 2
        print(f"Chunk {i}/{len(chunks)}: {bytes_count} bytes ({length_chars} chars)...")
        if upload_chunk(args.host, full_chunk, bytes_count):
            success_count += 1
        else:
            print("Upload failed. Stopping.")
            return 1

    if success_count == len(chunks):
        print("All chunks uploaded successfully!")

        # Trigger display refresh
        show_url = f"http://{args.host}/show"
        try:
            print("Refreshing display...")
            response = requests.get(show_url, timeout=30)
            if response.status_code == 200:
                print(f"Show: {response.text.strip()}")
                print("Done!")
                return 0
            else:
                print(f"Show failed: {response.status_code} - {response.text.strip()}")
                return 1
        except requests.exceptions.RequestException as e:
            print(f"Show error: {e}")
            return 1
    else:
        print(f"Only {success_count}/{len(chunks)} chunks succeeded")
        return 1


if __name__ == "__main__":
    sys.exit(main())
