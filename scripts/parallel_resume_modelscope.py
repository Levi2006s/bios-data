#!/usr/bin/env python3
"""Safely resume one large ModelScope file with parallel HTTP ranges.

The existing ``.incomplete`` file is treated as an immutable verified prefix.
Downloaded ranges and the prefix are only promoted to the final path after the
assembled file matches the repository SHA-256 digest.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from modelscope_hub import HubApi


MIB = 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-type", default="dataset")
    parser.add_argument("--revision", default="master")
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--local-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--part-size-mib", type=int, default=64)
    parser.add_argument("--progress-interval", type=int, default=30)
    return parser.parse_args()


def remote_metadata(args: argparse.Namespace) -> tuple[int, str]:
    api = HubApi()
    if args.repo_type != "dataset":
        raise ValueError("This helper currently supports dataset repositories only")
    files = api.legacy.list_dataset_files_paginated(
        args.repo_id, revision=args.revision
    )
    for item in files:
        path = item.get("Path") or item.get("path") or item.get("Name")
        if path == args.file_path:
            size = int(item.get("Size") or item.get("size") or 0)
            sha256 = item.get("Sha256") or item.get("sha256") or ""
            if size <= 0 or len(sha256) != 64:
                raise RuntimeError("Remote file metadata lacks size or SHA-256")
            return size, sha256.lower()
    raise FileNotFoundError(f"Remote file not found: {args.file_path}")


def human_bytes(value: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def copy_and_hash(source: Path, output, digest: hashlib._Hash) -> None:
    with source.open("rb") as handle:
        while True:
            chunk = handle.read(16 * MIB)
            if not chunk:
                return
            output.write(chunk)
            digest.update(chunk)


def main() -> int:
    args = parse_args()
    if not 1 <= args.workers <= 16:
        raise ValueError("--workers must be between 1 and 16")
    if args.part_size_mib < 8:
        raise ValueError("--part-size-mib must be at least 8")

    target = args.local_dir / args.file_path
    prefix = target.with_suffix(target.suffix + ".incomplete")
    assembling = target.with_suffix(target.suffix + ".assembling")
    parts_dir = target.parent / f".{target.name}.parallel-parts"

    if target.exists():
        raise FileExistsError(f"Final target already exists: {target}")
    if not prefix.is_file():
        raise FileNotFoundError(f"Resume prefix not found: {prefix}")

    total_size, expected_sha256 = remote_metadata(args)
    prefix_size = prefix.stat().st_size
    if not 0 < prefix_size < total_size:
        raise RuntimeError(
            f"Invalid prefix size {prefix_size}; remote size is {total_size}"
        )

    free_bytes = shutil.disk_usage(target.parent).free
    if free_bytes < total_size + 512 * MIB:
        raise RuntimeError(
            f"Need at least {human_bytes(total_size + 512 * MIB)} free for safe assembly; "
            f"only {human_bytes(free_bytes)} available"
        )

    parts_dir.mkdir(parents=True, exist_ok=True)
    part_size = args.part_size_mib * MIB
    ranges: list[tuple[int, int, Path]] = []
    start = prefix_size
    while start < total_size:
        end = min(total_size - 1, start + part_size - 1)
        ranges.append((start, end, parts_dir / f"{start}-{end}.part"))
        start = end + 1

    thread_state = threading.local()

    def client() -> HubApi:
        if not hasattr(thread_state, "api"):
            thread_state.api = HubApi()
        return thread_state.api

    def download_range(task: tuple[int, int, Path]) -> None:
        range_start, range_end, part_path = task
        expected = range_end - range_start + 1
        for attempt in range(1, 7):
            existing = part_path.stat().st_size if part_path.exists() else 0
            if existing == expected:
                return
            if existing > expected:
                raise RuntimeError(f"Oversized part: {part_path}")
            request_start = range_start + existing
            response = None
            try:
                response = client().legacy.download_stream(
                    args.repo_id,
                    args.repo_type,
                    args.file_path,
                    args.revision,
                    headers={"Range": f"bytes={request_start}-{range_end}"},
                )
                content_range = response.headers.get("Content-Range", "")
                if response.status_code != 206 or not content_range.startswith(
                    f"bytes {request_start}-{range_end}/"
                ):
                    raise RuntimeError(
                        f"Server rejected byte range {request_start}-{range_end}: "
                        f"status={response.status_code}, Content-Range={content_range!r}"
                    )
                with part_path.open("ab") as output:
                    for chunk in response.iter_content(chunk_size=MIB):
                        if chunk:
                            output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if part_path.stat().st_size == expected:
                    return
                raise RuntimeError(f"Short part download: {part_path}")
            except Exception as exc:
                if attempt == 6:
                    raise RuntimeError(
                        f"Range {range_start}-{range_end} failed after {attempt} attempts"
                    ) from exc
                time.sleep(min(2 ** attempt, 30))
            finally:
                if response is not None:
                    response.close()

    def completed_part_bytes() -> int:
        total = 0
        for range_start, range_end, path in ranges:
            if path.exists():
                total += min(path.stat().st_size, range_end - range_start + 1)
        return total

    stop_monitor = threading.Event()
    initial_part_bytes = completed_part_bytes()
    monitor_started = time.monotonic()

    def monitor() -> None:
        while not stop_monitor.wait(args.progress_interval):
            downloaded = completed_part_bytes()
            elapsed = max(time.monotonic() - monitor_started, 1e-9)
            rate = max(downloaded - initial_part_bytes, 0) / elapsed
            remaining = total_size - prefix_size - downloaded
            eta = remaining / rate if rate > 0 else float("inf")
            eta_text = f"{eta / 60:.1f} min" if eta != float("inf") else "unknown"
            print(
                f"progress={100 * (prefix_size + downloaded) / total_size:.2f}% "
                f"new_rate={human_bytes(rate)}/s eta={eta_text}",
                flush=True,
            )

    print(
        f"remote={human_bytes(total_size)} prefix={human_bytes(prefix_size)} "
        f"remaining={human_bytes(total_size - prefix_size)} workers={args.workers} "
        f"parts={len(ranges)}",
        flush=True,
    )
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(download_range, task) for task in ranges]
            for future in as_completed(futures):
                future.result()
    finally:
        stop_monitor.set()
        monitor_thread.join(timeout=2)

    if prefix.stat().st_size != prefix_size:
        raise RuntimeError("Resume prefix changed during parallel download; refusing assembly")

    print("All ranges downloaded; assembling and verifying SHA-256...", flush=True)
    digest = hashlib.sha256()
    with assembling.open("wb") as output:
        copy_and_hash(prefix, output, digest)
        for _start, _end, part_path in ranges:
            copy_and_hash(part_path, output, digest)
        output.flush()
        os.fsync(output.fileno())

    actual_size = assembling.stat().st_size
    actual_sha256 = digest.hexdigest()
    if actual_size != total_size or actual_sha256 != expected_sha256:
        raise RuntimeError(
            "Integrity verification failed; prefix, parts, and assembled file were retained. "
            f"size={actual_size}/{total_size}, sha256={actual_sha256}/{expected_sha256}"
        )

    os.replace(assembling, target)
    prefix.unlink()
    for _start, _end, part_path in ranges:
        part_path.unlink(missing_ok=True)
    parts_dir.rmdir()
    print(
        f"COMPLETE path={target} size={actual_size} sha256={actual_sha256}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
