#!/usr/bin/env python3
"""
Convert EPD binary files to C array source code.

This tool reads a .bin file (output from geink convert) and generates
a C header file with the binary data as a const uint8_t array.

The output includes:
1. Pre-inverted data (~byte) for ESPSlider 7.5 V2 compatibility
2. Include guards
3. Array size definition

Usage:
    python tools/bin_to_c_array.py input.bin array_name > output.h
"""

import argparse
import sys
from pathlib import Path


def bin_to_c_array(
    bin_file: str,
    array_name: str,
    bytes_per_line: int = 12,
    invert: bool = True,
) -> str:
    """
    Convert binary file to C array source code.

    Args:
        bin_file: Path to input .bin file
        array_name: Name for the C array (e.g., "image1_data")
        bytes_per_line: Number of bytes per line in output (default: 12)
        invert: If True, invert all bytes (~byte) for ESPSlider compatibility

    Returns:
        C header file content as string
    """
    bin_path = Path(bin_file)
    if not bin_path.exists():
        raise FileNotFoundError(f"Binary file not found: {bin_file}")

    # Read binary data
    with open(bin_path, "rb") as f:
        data = f.read()

    data_size = len(data)

    # Build header content
    lines = []
    guard_name = f"{array_name.upper()}_H"

    # Header guard
    lines.append(f"#ifndef {guard_name}")
    lines.append(f"#define {guard_name}")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("#include <pgmspace.h>")
    lines.append("")

    # Array definition - force to Flash using PROGMEM
    lines.append(f"// Size: {data_size} bytes ({data_size / 1024:.1f} KB)")
    lines.append(f"// Source: {bin_path.name}")
    if invert:
        lines.append("// Data pre-inverted (~byte) for ESPSlider 7.5 V2")
    lines.append("// Stored in Flash using PROGMEM")
    lines.append(f"const uint8_t {array_name}[{data_size}] PROGMEM = {{")

    # Convert data to hex array
    for i in range(0, data_size, bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_values = []

        for byte in chunk:
            # Invert if needed (ESPSlider 7.5 V2 requires ~byte)
            value = (~byte) & 0xFF if invert else byte
            hex_values.append(f"0x{value:02X}")

        lines.append(f"    {', '.join(hex_values)},")

    # Close array
    lines.append("};")
    lines.append("")
    lines.append(f"#endif // {guard_name}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert EPD binary file to C array source code"
    )
    parser.add_argument("bin_file", help="Input .bin file path")
    parser.add_argument("array_name", help="C array name (e.g., 'image1_data')")
    parser.add_argument(
        "--bytes-per-line",
        type=int,
        default=12,
        help="Bytes per line in output (default: 12)",
    )
    parser.add_argument(
        "--no-invert",
        action="store_true",
        help="Don't invert bytes (default: invert for ESPSlider)",
    )

    args = parser.parse_args()

    try:
        output = bin_to_c_array(
            args.bin_file,
            args.array_name,
            args.bytes_per_line,
            invert=not args.no_invert,
        )
        print(output)
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
