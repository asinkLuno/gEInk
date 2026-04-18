#!/usr/bin/env python3
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).parent / "tests"
ALPHA = 0.7
DOT_RATIO = 0.002
JITTER = 0

jpg_files = sorted(TESTS_DIR.glob("*.jpg"))
for jpg in jpg_files:
    out = jpg.with_name(f"{jpg.stem}_point.png")
    print(f"Processing {jpg.name} ...")
    subprocess.run(
        [
            "geink",
            "pointillize",
            str(jpg),
            "--alpha",
            str(ALPHA),
            "--dot-ratio",
            str(DOT_RATIO),
            "--jitter",
            str(JITTER),
        ]
    )
    print(f"  -> {out}")
