#!/usr/bin/env python3
"""Launch the logic simulator from the project root."""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    logsim_dir = root_dir / "logsim"
    sys.path.insert(0, str(logsim_dir))
    runpy.run_path(str(logsim_dir / "logsim.py"), run_name="__main__")
