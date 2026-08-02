from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.ranking.prepare import activate_split


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_primary_affinity_route_uses_certified_weight_and_separates_heads(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.csv"
    registry_path = tmp_path / "registry.csv"
    output_path = tmp_path / "output.csv"
    _write(
        input_path,
        [
            {"record_id": "kd", "source_file": "kd.csv", "paper_split": "train"},
            {"record_id": "ic50", "source_file": "ic50.csv", "paper_split": "train"},
        ],
    )
    _write(
        registry_path,
        [
            {
                "source_file": "kd.csv",
                "tier": "Gold",
                "metric": "KD",
                "affinity_grade": "B/C",
                "training_head": "affinity_kd",
                "primary_affinity_weight": "0.625",
                "certification_version": "test",
            },
            {
                "source_file": "ic50.csv",
                "tier": "Gold",
                "metric": "IC50",
                "affinity_grade": "C",
                "training_head": "neutralization_ic50",
                "primary_affinity_weight": "0",
                "certification_version": "test",
            },
        ],
    )

    report = activate_split(
        input_path,
        output_path,
        split_column="paper_split",
        label_registry_path=registry_path,
    )

    assert report["rows"] == 1
    assert report["excluded_by_training_head"] == {"neutralization_ic50": 1}
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["record_id"] == "kd"
    assert row["label_quality"] == "0.625"
    assert row["affinity_grade"] == "B/C"


def test_committed_certification_has_complete_coverage_and_key_corrections() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "configs/label_registry.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 83
    lookup = {Path(row["source_file"]).name: row for row in rows}

    abrank = lookup["AbRank_dataset.csv"]
    assert abrank["direction"] == "0"
    assert abrank["supervised_use"] == "conditional"
    assert abrank["primary_affinity_weight"] == "0"

    for filename in (
        "makowski2022cooptimization_iso_ova.csv",
        "makowski2022cooptimization_igg_ova.csv",
    ):
        assert lookup[filename]["direction"] == "-1"
        assert lookup[filename]["training_head"] == "developability_ova_risk"

    assert sum(bool(row["filename_alias"]) for row in rows) == 1
    assert all(row["certification_version"] for row in rows)
