#!/bin/bash
# Pipeline: preprocess -> dither -> convert -> upload a single image to EPD

set -e

# Usage: ./run_upload.sh <image_path> [host]
# Example: ./run_upload.sh ./test_img/photo.jpg
#          ./run_upload.sh ./test_img/photo.jpg 192.168.10.211

if [ -z "$1" ]; then
    echo "Usage: $0 <image_path> [host]"
    echo "Example: $0 ./test_img/photo.jpg"
    exit 1
fi

INPUT="$1"
HOST="${2:-192.168.10.211}"

if [ ! -f "$INPUT" ]; then
    echo "Error: File not found: $INPUT"
    exit 1
fi

INPUT_ABS=$(realpath "$INPUT")
INPUT_DIR=$(dirname "$INPUT_ABS")
FILENAME=$(basename "$INPUT_ABS")
STEM="${FILENAME%.*}"

TEMP_CROP="$INPUT_DIR/${STEM}_crop.png"
TEMP_DITHERED="$INPUT_DIR/${STEM}_dithered.png"
OUTPUT_BIN="$INPUT_DIR/${STEM}.bin"

echo "=== Step 1: Preprocess ==="
geink preprocess "$INPUT_ABS" "$TEMP_CROP"

echo ""
echo "=== Step 2: Dither ==="
geink dither "$TEMP_CROP"

echo ""
echo "=== Step 3: Convert to .bin ==="
geink convert "$TEMP_DITHERED"

echo ""
echo "=== Step 4: Upload to EPD ==="
geink upload "$OUTPUT_BIN" "$HOST"

echo ""
echo "Done! Uploaded: $FILENAME"
