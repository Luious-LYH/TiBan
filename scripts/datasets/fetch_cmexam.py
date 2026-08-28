"""Documented fetch command; raw data is intentionally kept outside Git."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(); parser.add_argument("--dest", default="data/external/CMExam"); args = parser.parse_args(); dest = Path(args.dest)
if (dest / ".git").exists(): print(f"CMExam already present at {dest}")
else: subprocess.run(["git", "clone", "--depth", "1", "https://github.com/williamliujl/CMExam.git", str(dest)], check=True)
