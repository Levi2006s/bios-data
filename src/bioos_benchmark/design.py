from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

import joblib
import numpy as np

from .data import AA20, normalize_sequence


AA = "ACDEFGHIKLMNPQRSTVWY"


def mutate(
    sequence: str,
    rng: random.Random,
    max_mutations: int,
    mutable_positions: list[int] | None = None,
    protect_cysteine: bool = True,
) -> str:
    chars = list(sequence)
    positions = mutable_positions if mutable_positions is not None else list(range(len(chars)))
    positions = sorted(set(positions))
    if any(position < 0 or position >= len(chars) for position in positions):
        raise ValueError("mutable positions must be zero-based indices inside cdrh3")
    if protect_cysteine:
        positions = [position for position in positions if chars[position] != "C"]
    if not positions:
        raise ValueError("no mutable CDR-H3 positions remain after applying constraints")
    count = rng.randint(1, min(max_mutations, len(positions)))
    for position in rng.sample(positions, count):
        choices = [aa for aa in AA if aa != chars[position]]
        chars[position] = rng.choice(choices)
    return "".join(chars)


def mutation_notation(parent: str, candidate: str) -> tuple[str, int]:
    if len(parent) != len(candidate):
        raise ValueError("parent and candidate must have equal length")
    changes = [f"{left}{index + 1}{right}" for index, (left, right) in enumerate(zip(parent, candidate)) if left != right]
    return ";".join(changes), len(changes)


def liabilities(sequence: str) -> dict[str, float]:
    length = max(len(sequence), 1)
    glyco = len(re.findall(r"N[^P][ST]", sequence))
    hydrophobic = sum(x in "AVILMFWY" for x in sequence) / length
    charge = (sum(x in "KRH" for x in sequence) - sum(x in "DE" for x in sequence)) / length
    cysteine = sequence.count("C")
    deamidation = len(re.findall(r"N[GSHT]", sequence))
    isomerization = len(re.findall(r"D[GST]", sequence))
    oxidation = sequence.count("M") + sequence.count("W")
    # A paired VH/VL variable domain normally contains four conserved cysteines.
    penalty = (
        0.08 * glyco + 0.04 * max(cysteine - 4, 0)
        + 0.3 * max(hydrophobic - 0.45, 0)
        + 0.01 * deamidation + 0.01 * isomerization
    )
    return {
        "glycosylation_motifs": glyco,
        "hydrophobic_fraction": hydrophobic,
        "charge_density": charge,
        "cysteine_count": cysteine,
        "deamidation_motifs": deamidation,
        "isomerization_motifs": isomerization,
        "oxidation_residues": oxidation,
        "liability_penalty": penalty,
    }


def generate_candidates(target: dict[str, str], count: int, max_mutations: int, seed: int) -> list[dict[str, str]]:
    heavy = normalize_sequence(target.get("heavy", ""))
    light = normalize_sequence(target.get("light", ""))
    antigen_seq = normalize_sequence(target.get("antigen_seq", ""))
    cdrh3 = normalize_sequence(target.get("cdrh3", ""))
    if not heavy or not cdrh3 or cdrh3 not in heavy:
        raise ValueError("target.json must contain a valid heavy sequence and its exact cdrh3 substring.")
    rng = random.Random(seed)
    configured_positions = target.get("mutable_positions")
    mutable_positions = [int(value) for value in configured_positions] if configured_positions is not None else None
    protect_cysteine = bool(target.get("protect_cysteine", True))
    seen = {cdrh3}
    rows = []
    attempts = 0
    while len(rows) < count and attempts < count * 20:
        attempts += 1
        candidate_cdr = mutate(cdrh3, rng, max_mutations, mutable_positions, protect_cysteine)
        if candidate_cdr in seen:
            continue
        seen.add(candidate_cdr)
        candidate_heavy = heavy.replace(cdrh3, candidate_cdr, 1)
        notation, mutation_count = mutation_notation(cdrh3, candidate_cdr)
        rows.append(
            {
                "heavy": candidate_heavy,
                "light": light,
                "antigen_seq": antigen_seq,
                "cdrh3": candidate_cdr,
                "mutations": notation,
                "mutation_count": mutation_count,
            }
        )
    return rows


def _predict(bundle: dict[str, object], rows: list[dict[str, str]]) -> np.ndarray:
    model = bundle.get("model", bundle.get("global_model"))
    if model is None or "featurizer" not in bundle:
        raise ValueError("model bundle must contain a model/global_model and featurizer")
    return np.clip(model.predict(bundle["featurizer"].transform(rows)), 0, 1)


def design(model_path: Path, target_path: Path, output: Path, count: int, max_mutations: int, seed: int) -> dict[str, object]:
    bundle = joblib.load(model_path)
    target = json.loads(target_path.read_text(encoding="utf-8"))
    rows = generate_candidates(target, count, max_mutations, seed)
    predictions = _predict(bundle, rows)
    parent_row = {key: normalize_sequence(target.get(key, "")) for key in ("heavy", "light", "antigen_seq")}
    parent_prediction = float(_predict(bundle, [parent_row])[0])
    parent_risk = liabilities(parent_row["heavy"] + parent_row["light"])
    ranked = []
    for row, prediction in zip(rows, predictions):
        risk = liabilities(row["heavy"] + row["light"])
        ranked.append(
            {
                **row,
                "predicted_score": float(prediction),
                "parent_predicted_score": parent_prediction,
                "predicted_delta": float(prediction) - parent_prediction,
                **risk,
                "liability_delta": risk["liability_penalty"] - parent_risk["liability_penalty"],
                "composite_score": float(prediction) - risk["liability_penalty"] - 0.01 * row["mutation_count"],
                "evidence_status": "in_silico_unvalidated",
            }
        )
    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ranked[0]))
        writer.writeheader()
        writer.writerows(ranked)
    report = {
        "output": str(output), "candidates": len(ranked), "seed": seed,
        "max_mutations": max_mutations, "parent_predicted_score": parent_prediction,
        "warning": "Predictions are retrospective model scores, not experimental affinity claims.",
    }
    output.with_suffix(".summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and rank CDR-H3 variants.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/candidates.csv"))
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--max-mutations", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260722)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = design(args.model, args.target, args.output, args.count, args.max_mutations, args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
