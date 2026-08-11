import csv
from pathlib import Path

from bioos_benchmark.inner_family_split import build_inner_split


def test_inner_split_excludes_outer_validation_and_keeps_exact_family_together(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    rows = [
        {"record_id": "a", "heavy": "A" * 40, "light": "C" * 30, "task_route": "alphaseq_rank", "outer": "train"},
        {"record_id": "b", "heavy": "A" * 40, "light": "C" * 30, "task_route": "alphaseq_rank", "outer": "train"},
        {"record_id": "c", "heavy": "D" * 40, "light": "E" * 30, "task_route": "alphaseq_rank", "outer": "train"},
        {"record_id": "d", "heavy": "F" * 40, "light": "G" * 30, "task_route": "alphaseq_rank", "outer": "validation"},
    ]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)
    output = tmp_path / "inner.csv"
    build_inner_split(source, output, outer_column="outer", inner_column="inner", train_fraction=0.5)
    with output.open(encoding="utf-8", newline="") as handle:
        result = list(csv.DictReader(handle))
    assert result[0]["inner"] == result[1]["inner"]
    assert result[3]["inner"] == "excluded"

