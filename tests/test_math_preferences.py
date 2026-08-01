from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.ranking.preferences import (
    build_preference_pairs,
    main,
    validate_preference_pairs,
)


def sample_rows() -> list[dict[str, object]]:
    return [
        {
            "record_id": "a",
            "source_file": "paper/data.csv",
            "antigen_id": "x",
            "score": "0.1",
            "split": "train",
            "label_quality": "1.0",
        },
        {
            "record_id": "b",
            "source_file": "paper/data.csv",
            "antigen_id": "x",
            "score": "0.5",
            "split": "train",
            "label_quality": "0.8",
        },
        {
            "record_id": "c",
            "source_file": "paper/data.csv",
            "antigen_id": "x",
            "score": "0.9",
            "split": "train",
            "label_quality": "1.0",
        },
        {
            "record_id": "d",
            "source_file": "paper/data.csv",
            "antigen_id": "x",
            "score": "0.9",
            "split": "train",
            "label_quality": "1.0",
        },
        {
            "record_id": "e",
            "source_file": "other/data.csv",
            "antigen_id": "y",
            "score": "0.2",
            "split": "validation",
        },
    ]


def test_build_preference_pairs_is_grouped_weighted_and_reproducible() -> None:
    rows = sample_rows()
    first = build_preference_pairs(rows, seed=7)
    second = build_preference_pairs(rows, seed=7)

    assert first == second
    assert len(first) == 5
    assert all(pair.preference == 1 for pair in first)
    assert all(0 < pair.pair_weight <= 1 for pair in first)
    assert all(pair.left_record_id not in {"a"} for pair in first)
    assert not any(
        {pair.left_record_id, pair.right_record_id} == {"c", "d"} for pair in first
    )
    report = validate_preference_pairs(first, rows)
    assert report["valid"] is True
    assert report["comparison_groups"] == 1


def test_double_censored_and_cross_split_pairs_are_not_created() -> None:
    rows = sample_rows()[:3]
    rows[0]["is_censored"] = "1"
    rows[1]["is_censored"] = "1"
    rows[2]["split"] = "validation"
    pairs = build_preference_pairs(rows)
    assert pairs == []


def test_raw_label_direction_fallback() -> None:
    rows = [
        {
            "record_id": "low_kd",
            "source_file": "kd.csv",
            "antigen_id": "x",
            "raw_label": "1",
            "direction": "-1",
        },
        {
            "record_id": "high_kd",
            "source_file": "kd.csv",
            "antigen_id": "x",
            "raw_label": "10",
            "direction": "-1",
        },
    ]
    pairs = build_preference_pairs(rows)
    assert pairs[0].left_record_id == "low_kd"


def test_global_pair_limit_is_source_balanced() -> None:
    rows = sample_rows()[:4]
    second_group = []
    for row in rows:
        copy = dict(row)
        copy["record_id"] = "second_" + str(copy["record_id"])
        copy["source_file"] = "second/data.csv"
        second_group.append(copy)
    pairs = build_preference_pairs(
        rows + second_group,
        max_pairs_per_group=10,
        max_pairs_total=2,
        seed=7,
    )
    assert len(pairs) == 2
    assert len({pair.comparison_group for pair in pairs}) == 2


def test_cli_writes_pairs_and_summary(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "records.csv"
    output_path = tmp_path / "pairs.csv"
    rows = sample_rows()
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.setattr(
        "sys.argv",
        [
            "bioos-build-pairs",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--split",
            "train",
        ],
    )
    main()
    assert output_path.exists()
    assert output_path.with_suffix(".summary.json").exists()
