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


def mutate(sequence: str, rng: random.Random, max_mutations: int) -> str:
    chars = list(sequence)
    count = rng.randint(1, min(max_mutations, len(chars)))
    for position in rng.sample(range(len(chars)), count):
        choices = [aa for aa in AA if aa != chars[position]]
        chars[position] = rng.choice(choices)
    return "".join(chars)


def liabilities(sequence: str) -> dict[str, float]:
    length = max(len(sequence), 1)
    glyco = len(re.findall(r"N[^P][ST]", sequence))
    hydrophobic = sum(x in "AVILMFWY" for x in sequence) / length
    charge = (sum(x in "KRH" for x in sequence) - sum(x in "DE" for x in sequence)) / length
    cysteine = sequence.count("C")
    # A paired VH/VL variable domain normally contains four conserved cysteines.
    penalty = 0.08 * glyco + 0.04 * max(cysteine - 4, 0) + 0.3 * max(hydrophobic - 0.45, 0)
    return {
        "glycosylation_motifs": glyco,
        "hydrophobic_fraction": hydrophobic,
        "charge_density": charge,
        "cysteine_count": cysteine,
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
    seen = {cdrh3}
    rows = []
    attempts = 0
    while len(rows) < count and attempts < count * 20:
        attempts += 1
        candidate_cdr = mutate(cdrh3, rng, max_mutations)
        if candidate_cdr in seen:
            continue
        seen.add(candidate_cdr)
        candidate_heavy = heavy.replace(cdrh3, candidate_cdr, 1)
        rows.append(
            {
                "heavy": candidate_heavy,
                "light": light,
                "antigen_seq": antigen_seq,
                "cdrh3": candidate_cdr,
            }
        )
    return rows


def design(model_path: Path, target_path: Path, output: Path, count: int, max_mutations: int, seed: int) -> None:
    bundle = joblib.load(model_path)
    target = json.loads(target_path.read_text(encoding="utf-8"))
    rows = generate_candidates(target, count, max_mutations, seed)
    predictions = np.clip(bundle["model"].predict(bundle["featurizer"].transform(rows)), 0, 1)
    ranked = []
    for row, prediction in zip(rows, predictions):
        risk = liabilities(row["heavy"] + row["light"])
        ranked.append(
            {
                **row,
                "predicted_score": float(prediction),
                **risk,
                "composite_score": float(prediction) - risk["liability_penalty"],
            }
        )
    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ranked[0]))
        writer.writeheader()
        writer.writerows(ranked)


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
    design(args.model, args.target, args.output, args.count, args.max_mutations, args.seed)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
