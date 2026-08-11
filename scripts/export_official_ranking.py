"""Export the official antigen-wise ranking table for the Bio-OS preliminary round."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd


def export_ranking(data_path: Path, predictions_path: Path, output_path: Path, team_name: str) -> dict[str, object]:
    predictions = pd.read_csv(predictions_path, usecols=["record_id", "prediction"])
    score_lookup = dict(zip(predictions["record_id"].astype(str), predictions["prediction"].astype(float)))
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    with data_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            record_id = str(row.get("record_id", ""))
            if record_id not in score_lookup:
                continue
            heavy, light = row.get("heavy", "").strip(), row.get("light", "").strip()
            if not heavy or not light:  # Current submission deliberately excludes VHH.
                continue
            antigen = row.get("antigen_id", "").strip() or row.get("antigen_seq", "").strip() or "UNKNOWN"
            grouped[(antigen, heavy, light)].append(score_lookup[record_id])

    rows = [
        {"Antigen": antigen, "VH/VHH": heavy, "VL": light, "_score": sum(scores) / len(scores)}
        for (antigen, heavy, light), scores in grouped.items()
    ]
    rows.sort(key=lambda row: (row["Antigen"], -row["_score"], row["VH/VHH"], row["VL"]))
    previous_antigen = None
    rank = 0
    for row in rows:
        if row["Antigen"] != previous_antigen:
            previous_antigen = row["Antigen"]
            rank = 1
        else:
            rank += 1
        row[team_name] = rank
        del row["_score"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["Antigen", "VH/VHH", "VL", team_name])
    frame.insert(3, "Rank 示例", "")
    if output_path.suffix.lower() == ".xlsx":
        frame.to_excel(output_path, index=False, sheet_name="Prediction")
    else:
        frame.to_csv(output_path, index=False)
    counts = frame.groupby("Antigen").size().astype(int).to_dict()
    return {"output": str(output_path), "rows": len(frame), "team_column": team_name, "rows_by_antigen": counts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--team-name", default="AbCompass")
    args = parser.parse_args()
    print(export_ranking(args.data, args.predictions, args.output, args.team_name))


if __name__ == "__main__":
    main()
