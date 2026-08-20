"""Parallel HTTP Range downloader with exact size and SHA256 verification."""

from __future__ import annotations

import argparse
import hashlib
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("output")
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retries", type=int, default=5)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    parts = output.parent / (output.name + ".parts")
    parts.mkdir(parents=True, exist_ok=True)
    chunk = (args.size + args.workers - 1) // args.workers

    def fetch(index: int) -> Path:
        start = index * chunk
        end = min(args.size, start + chunk) - 1
        expected = end - start + 1
        path = parts / f"part-{index:03d}"
        if path.exists() and path.stat().st_size == expected:
            print(f"part={index} status=reused bytes={expected}", flush=True)
            return path
        for attempt in range(1, args.retries + 1):
            try:
                request = urllib.request.Request(args.url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "model-eval-v21"})
                with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as stream:
                    if response.status != 206:
                        raise RuntimeError(f"part {index}: expected HTTP 206, got {response.status}")
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        stream.write(block)
                actual = path.stat().st_size
                if actual != expected:
                    raise RuntimeError(f"part {index}: expected {expected} bytes, got {actual}")
                print(f"part={index} status=downloaded bytes={actual}", flush=True)
                return path
            except Exception as exc:
                print(f"part={index} attempt={attempt} error={type(exc).__name__}:{exc}", flush=True)
                if attempt == args.retries:
                    raise
                time.sleep(attempt * 2)
        raise AssertionError("unreachable")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        completed = list(as_completed(pool.submit(fetch, index) for index in range(args.workers)))
        for future in completed:
            future.result()

    digest = hashlib.sha256()
    with output.open("wb") as merged:
        for index in range(args.workers):
            path = parts / f"part-{index:03d}"
            with path.open("rb") as stream:
                while True:
                    block = stream.read(4 * 1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    merged.write(block)
    actual_size = output.stat().st_size
    actual_sha = digest.hexdigest()
    if actual_size != args.size or actual_sha.lower() != args.sha256.lower():
        raise RuntimeError(f"verification failed: size={actual_size}, sha256={actual_sha}")
    print(f"status=verified output={output} size={actual_size} sha256={actual_sha}", flush=True)


if __name__ == "__main__":
    main()

