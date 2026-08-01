from __future__ import annotations

import csv
from pathlib import Path

from bioos_benchmark.data import AA20, RawRecord, normalize_sequence, percentile_scores
from bioos_benchmark.design import generate_candidates, liabilities
from bioos_benchmark.train import split_rows


def test_normalize_sequence() -> None:
    assert normalize_sequence("ACD-EF") == "ACDEF"
    assert normalize_sequence("ACDX") == ""


def test_percentile_direction() -> None:
    records = [
        RawRecord("a", "x", "", "AAA", "", "", 10.0, -1),
        RawRecord("a", "x", "", "AAA", "", "", 1.0, -1),
    ]
    assert percentile_scores(records) == [0.0, 1.0]


def test_source_split_has_no_overlap() -> None:
    rows = [{"source_file": f"source-{i}"} for i in range(20)]
    train, test = split_rows(rows, 20)
    assert train and test
    assert {x["source_file"] for x in train}.isdisjoint({x["source_file"] for x in test})


def test_candidate_generation() -> None:
    target = {
        "antigen_seq": "ACDEFG",
        "heavy": "AAAACDEFGHIKLLLL",
        "light": "ACDEFGHIK",
        "cdrh3": "CDEFGHIK",
    }
    rows = generate_candidates(target, count=10, max_mutations=2, seed=1)
    assert len(rows) == 10
    assert len({x["cdrh3"] for x in rows}) == 10
    assert all(set(x["heavy"]) <= AA20 for x in rows)
    assert liabilities(rows[0]["heavy"])["liability_penalty"] >= 0
