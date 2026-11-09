#!/usr/bin/env python3
"""共享 Core 检出的批量同步入口，可从任意当前目录调用。"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "skills/core-sync/scripts/core_sync.py"), run_name="__main__")
