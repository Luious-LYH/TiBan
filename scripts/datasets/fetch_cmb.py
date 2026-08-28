"""Documented CMB fetch command; raw data is intentionally kept outside Git."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(); parser.add_argument("--dest", default="data/external/CMB"); args = parser.parse_args(); dest = Path(args.dest); dest.mkdir(parents=True, exist_ok=True); archive = dest / "CMB-datasets.zip"
if not archive.exists(): subprocess.run(["curl", "-L", "-o", str(archive), "https://huggingface.co/datasets/FreedomIntelligence/CMB/resolve/main/CMB-datasets.zip"], check=True)
print(f"Downloaded/available: {archive}")
