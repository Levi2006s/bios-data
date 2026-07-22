from __future__ import annotations

import csv
import hashlib
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


AA20 = frozenset("ACDEFGHIKLMNPQRSTVWY")

ALIASES = {
    "heavy": (
        "heavy", "HC", "Ab_heavy_chain_seq", "Ab/Nano H_Chain AA", "sequence",
    ),
    "light": (
        "light", "LC", "Ab_light_chain_seq", "Ab/Nano L_Chain AA",
    ),
    "antigen_seq": (
        "antigen_seq", "Ag_seq", "Ag_Seq",
    ),
    "antigen_id": (
        "Antigen", "Target", "Ag_name", "Ag_Name", "name",
    ),
    "cdrh3": (
        "CDRH3", "HCDR3", "Ab/Nano_CDR H3",
    ),
    "label": (
        "fitness", "Pred_affinity", "KD [bind/no bind]", "Kd [M]",
    ),
}


@dataclass(frozen=True)
class RawRecord:
    source_file: str
    antigen_id: str
    antigen_seq: str
    heavy: str
    light: str
    cdrh3: str
    raw_label: float
    direction: int


def normalize_sequence(value: object) -> str:
    text = re.sub(r"[^A-Za-z]", "", str(value or "")).upper()
    return text if text and set(text) <= AA20 else ""


def parse_number(value: object) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text or text.lower() in {"na", "n/a", "nan", "none", "\\"}:
        return None
    lowered = text.lower()
    if lowered in {"true", "bind", "binder", "positive", "yes"}:
        return 1.0
    if lowered in {"false", "no bind", "nonbinder", "negative", "no"}:
        return 0.0
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _find_key(fieldnames: Iterable[str], aliases: Iterable[str]) -> str | None:
    names = {str(name).strip().casefold(): name for name in fieldnames if name is not None}
    for alias in aliases:
        hit = names.get(alias.strip().casefold())
        if hit is not None:
            return hit
    return None


def _header_and_rows(path: Path) -> tuple[list[str], Iterator[list[str]]]:
    handle = path.open("r", encoding="utf-8-sig", errors="replace", newline="")
    reader = csv.reader(handle)
    header: list[str] = []
    for _ in range(80):
        try:
            candidate = next(reader)
        except StopIteration:
            break
        folded = {str(x).strip().casefold() for x in candidate}
        if folded & {"heavy", "hc", "ab_heavy_chain_seq", "sequence"}:
            header = candidate
            break

    def rows() -> Iterator[list[str]]:
        try:
            yield from reader
        finally:
            handle.close()

    return header, rows()


def infer_direction(fieldnames: Iterable[str], label_key: str) -> int:
    """Return +1 when larger values are better, otherwise -1."""
    label = label_key.casefold()
    headers = " | ".join(str(x).casefold() for x in fieldnames)
    if any(token in label for token in ("neg_log", "neg log", "-log", "fitness")):
        # A fitness column often copies a transformed value. Detect an explicit transform first.
        if any(token in headers for token in ("neg_log", "neg log", "-log", "log_aff")):
            return 1
    if any(token in headers for token in ("bind/no bind", "binary")):
        return 1
    if any(token in headers for token in ("kd", "ic50", "ec50", "affinity")):
        return -1
    return 1


def iter_csv_records(
    path: Path, data_root: Path, direction_override: int | None = None
) -> Iterator[RawRecord]:
    header, raw_rows = _header_and_rows(path)
    if not header:
        return
    keys = {name: _find_key(header, aliases) for name, aliases in ALIASES.items()}
    if not keys["heavy"] or not keys["label"]:
        return
    direction = direction_override if direction_override in {-1, 1} else infer_direction(header, keys["label"])
    source = path.relative_to(data_root).as_posix()
    for values in raw_rows:
        if len(values) < len(header):
            values += [""] * (len(header) - len(values))
        row = dict(zip(header, values))
        heavy = normalize_sequence(row.get(keys["heavy"], ""))
        light = normalize_sequence(row.get(keys["light"], "")) if keys["light"] else ""
        antigen_seq = normalize_sequence(row.get(keys["antigen_seq"], "")) if keys["antigen_seq"] else ""
        cdrh3 = normalize_sequence(row.get(keys["cdrh3"], "")) if keys["cdrh3"] else ""
        label = parse_number(row.get(keys["label"], ""))
        if not heavy or label is None:
            continue
        antigen_id = str(row.get(keys["antigen_id"], "") or path.stem).strip() if keys["antigen_id"] else path.stem
        yield RawRecord(source, antigen_id, antigen_seq, heavy, light, cdrh3, label, direction)


def reservoir_sample(records: Iterable[RawRecord], limit: int | None, seed: int) -> list[RawRecord]:
    if not limit or limit <= 0:
        return list(records)
    rng = random.Random(seed)
    sample: list[RawRecord] = []
    for index, record in enumerate(records):
        if index < limit:
            sample.append(record)
            continue
        replacement = rng.randint(0, index)
        if replacement < limit:
            sample[replacement] = record
    return sample


def percentile_scores(records: list[RawRecord]) -> list[float]:
    if not records:
        return []
    oriented = [record.raw_label * record.direction for record in records]
    order = sorted(range(len(oriented)), key=lambda idx: oriented[idx])
    scores = [0.5] * len(records)
    if len(order) == 1:
        return scores
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and oriented[order[end]] == oriented[order[start]]:
            end += 1
        average_rank = (start + end - 1) / 2
        percentile = average_rank / (len(order) - 1)
        for position in range(start, end):
            scores[order[position]] = percentile
        start = end
    return scores


def stable_bucket(value: str, modulo: int = 100) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % modulo


def source_group(source_file: str) -> str:
    """Return the numbered literature dataset directory used for leakage-safe splits."""
    parts = source_file.replace("\\", "/").split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else source_file


def stable_record_id(record: RawRecord) -> str:
    payload = "\x1f".join(
        [
            record.source_file,
            record.antigen_id,
            record.antigen_seq,
            record.heavy,
            record.light,
            record.cdrh3,
            f"{record.raw_label:.12g}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
