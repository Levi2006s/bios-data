#!/usr/bin/env python3
"""Verify a local ModelScope dataset snapshot against remote metadata."""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

from modelscope_hub import HubApi


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-type", default="dataset")
    parser.add_argument("--revision", default="master")
    parser.add_argument("--local-dir", type=Path, required=True)
    parser.add_argument("--test-zip", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(16 * 1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def main() -> int:
    args = parse_args()
    if args.repo_type != "dataset":
        raise ValueError("This verifier currently supports dataset repositories only")
    local_dir = args.local_dir.resolve()
    if not local_dir.is_dir():
        raise NotADirectoryError(local_dir)

    raw_files = HubApi().legacy.list_dataset_files_paginated(
        args.repo_id, revision=args.revision
    )
    expected: dict[str, tuple[int, str]] = {}
    for item in raw_files:
        path = item.get("Path") or item.get("path") or item.get("Name") or ""
        kind = item.get("Type") or item.get("type") or "blob"
        if not path or kind == "tree":
            continue
        size = int(item.get("Size") or item.get("size") or 0)
        sha256 = (item.get("Sha256") or item.get("sha256") or "").lower()
        expected[path] = (size, sha256)

    actual = {
        path.relative_to(local_dir).as_posix(): path
        for path in local_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    errors: list[str] = []
    errors.extend(f"missing: {path}" for path in missing)
    errors.extend(f"extra: {path}" for path in extra)

    checked_bytes = 0
    zip_paths: list[Path] = []
    for index, relative in enumerate(sorted(set(expected) & set(actual)), start=1):
        path = actual[relative]
        expected_size, expected_sha256 = expected[relative]
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            errors.append(
                f"size mismatch: {relative}: {actual_size} != {expected_size}"
            )
            continue
        if len(expected_sha256) != 64:
            errors.append(f"missing remote SHA-256: {relative}")
            continue
        actual_sha256 = sha256_file(path)
        if actual_sha256 != expected_sha256:
            errors.append(
                f"SHA-256 mismatch: {relative}: {actual_sha256} != {expected_sha256}"
            )
        checked_bytes += actual_size
        if path.suffix.lower() in {".zip", ".xlsx"}:
            zip_paths.append(path)
        if index % 10 == 0 or index == len(expected):
            print(
                f"hash {index}/{len(expected)} {relative}",
                flush=True,
            )

    if args.test_zip:
        for index, path in enumerate(zip_paths, start=1):
            relative = path.relative_to(local_dir).as_posix()
            try:
                with zipfile.ZipFile(path) as archive:
                    bad_member = archive.testzip()
                if bad_member is not None:
                    errors.append(f"ZIP CRC failure: {relative}: {bad_member}")
                else:
                    print(
                        f"zip {index}/{len(zip_paths)} OK {relative}",
                        flush=True,
                    )
            except Exception as exc:
                errors.append(f"ZIP test failed: {relative}: {exc}")

    print(
        f"SUMMARY expected={len(expected)} actual={len(actual)} "
        f"checked_bytes={checked_bytes} errors={len(errors)}",
        flush=True,
    )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("VERIFIED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
