"""Export deduplicated non-VHH antibody sequences with final Stage 21 scores."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from pathlib import Path

import pandas as pd


def sequence_id(heavy: str, light: str) -> str:
    digest = hashlib.sha256(f"{heavy}\x1f{light}".encode()).hexdigest()[:20]
    return f"AB-{digest}"


def export_sequences(data_path: Path, predictions_path: Path, output_path: Path) -> dict[str, int]:
    predictions = pd.read_csv(predictions_path, usecols=["record_id", "prediction"])
    score_lookup = dict(zip(predictions["record_id"].astype(str), predictions["prediction"].astype(float)))
    pairs: dict[tuple[str, str], dict[str, object]] = {}
    with data_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("task_route") != "alphaseq_rank" or row.get("global_family_v2_split") != "validation":
                continue
            heavy, light = row.get("heavy", "").strip(), row.get("light", "").strip()
            if not heavy or not light:  # VHH and incomplete pairs are deliberately excluded.
                continue
            record_id = str(row["record_id"])
            if record_id not in score_lookup:
                continue
            key = (heavy, light)
            current = pairs.setdefault(key, {"scores": [], "sources": set()})
            current["scores"].append(score_lookup[record_id])
            current["sources"].add(row.get("source_file", ""))

    ranked = sorted(
        (
            {
                "sequence_id": sequence_id(heavy, light),
                "heavy": heavy,
                "light": light,
                "score": sum(meta["scores"]) / len(meta["scores"]),
                "source_count": len(meta["sources"]),
            }
            for (heavy, light), meta in pairs.items()
        ),
        key=lambda row: (-row["score"], row["sequence_id"]),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if output_path.suffix == ".gz" else open
    with opener(output_path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sequence_id", "rank", "score", "heavy", "light", "source_count"])
        writer.writeheader()
        for rank, row in enumerate(ranked, start=1):
            writer.writerow({"rank": rank, **row})
    return {"unique_non_vhh_pairs": len(ranked), "scored_records": len(predictions)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(export_sequences(args.data, args.predictions, args.output))


if __name__ == "__main__":
    main()
