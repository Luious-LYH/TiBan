"""Download the small upstream ARC Easy train parquet to an ignored local path."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlretrieve

from app.core.config import ARC_EASY_ROOT


URL = "https://huggingface.co/datasets/allenai/ai2_arc/resolve/refs%2Fconvert%2Fparquet/ARC-Easy/train/0000.parquet"


def main() -> None:
    ARC_EASY_ROOT.mkdir(parents=True, exist_ok=True)
    target = ARC_EASY_ROOT / "arc_easy_train.parquet"
    if not target.is_file():
        urlretrieve(URL, target)
    print(target)


if __name__ == "__main__":
    main()
