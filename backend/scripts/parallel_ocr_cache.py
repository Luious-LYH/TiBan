"""Temporary local helper for filling the page OCR cache in parallel.

The production actor still owns document parsing and the final database
commit.  This helper only computes the existing runtime-only page cache, so a
large scan can use several independent OCR runtimes without changing the
document contract or introducing partial knowledge records.
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def _process_batch(arguments: tuple[str, str, list[int]]) -> int:
    source_name, cache_key, pages = arguments
    import fitz

    from app.services.document_parser import _ocr_page_cache_exists, _ocr_page_elements

    completed = 0
    pdf = fitz.open(source_name)
    try:
        for page_number in pages:
            if _ocr_page_cache_exists(cache_key, page_number):
                continue
            _ocr_page_elements(
                pdf[page_number - 1],
                page_number,
                "导言",
                None,
                cache_key=cache_key,
            )
            completed += 1
    finally:
        pdf.close()
    return completed


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: parallel_ocr_cache.py <pdf>")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.document_parser import OCR_CACHE_ROOT, _ocr_source_cache_key

    source = Path(sys.argv[1]).resolve()
    if not source.is_file():
        raise SystemExit(f"source not found: {source}")
    cache_key = _ocr_source_cache_key(source)
    total_pages = len(__import__("fitz").open(source))
    workers = min(3, max(1, total_pages // 120))
    page_batches = [list(range(start, total_pages + 1, workers)) for start in range(1, workers + 1)]
    arguments = [(str(source), cache_key, batch) for batch in page_batches]
    print(f"source={source.name} pages={total_pages} workers={workers} cache={OCR_CACHE_ROOT / cache_key}", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index, completed in enumerate(pool.map(_process_batch, arguments), start=1):
            print(f"batch {index}/{workers}: computed {completed} pages", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
