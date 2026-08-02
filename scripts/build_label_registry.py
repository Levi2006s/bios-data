"""Build the human-reviewed Bio-OS label registry from the audited file list.

The decisions in ``classify`` were reviewed against the supplied papers and the
original measurement columns.  Keeping the rules in code makes the CSV easy to
regenerate and review when the competition data changes.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


PAPERS = {
    "1": "Assessment and incorporation of in vitro correlates to pharmacokinetic outcomes in antibody developability workflows",
    "2": "Unlocking de novo antibody design with generative artificial intelligence",
    "3": "Machine learning optimization of candidate antibody yields highly diverse sub-nanomolar affinity antibody libraries",
    "4": "AbRank: A Benchmark Dataset and Metric-Learning Framework for Antibody-Antigen Affinity Ranking",
    "5": "Measuring the sequence-affinity landscape of antibodies with massively parallel titration curves",
    "6": "A dataset comprised of binding interactions for 104,972 antibodies against a SARS-CoV-2 peptide",
    "7": "Efficient evolution of human antibodies from general protein language models",
    "8": "Toward enhancement of antibody thermostability and affinity by computational design in the absence of antigen",
    "9": "Retrospective SARS-CoV-2 human antibody development trajectories are largely sparse and permissive",
    "10": "Mutational landscape of antibody variable domains reveals a switch modulating interdomain dynamics and antigen binding",
    "11": "High-Throughput Machine Learning-Aided Antibody Discovery for Cell Surface Antigens",
    "12": "Co-optimization of therapeutic antibody affinity and specificity using machine learning",
    "13": "Binding affinity landscapes constrain the evolution of broadly neutralizing anti-influenza antibodies",
    "14": "Ab-CoV: binding affinity and neutralization profiles of coronavirus-related antibodies",
    "15": "Automated optimisation of solubility and conformational stability of antibodies and proteins",
    "16": "IgDesign: in vitro validated antibody design using inverse folding",
    "17": "Unsupervised evolution of protein and antibody complexes with a structure-informed language model",
    "18": "AVIDa-hIL6: a large-scale VHH interaction dataset",
    "19": "A SARS-CoV-2 interaction dataset and VHH sequence corpus for antibody language models",
    "20": "Optimizing antibody affinity and stability by automated VH-VL interface design",
    "21": "Antibody evolution constrains conformational heterogeneity by tailoring protein dynamics",
    "22": "No supplied paper; ProteinBase auxiliary export",
}

YEARS = {
    "1": 2024, "2": 2023, "3": 2023, "4": 2025, "5": 2017, "6": 2022,
    "7": 2023, "8": 2023, "9": 2024, "10": 2017, "11": 2025, "12": 2022,
    "13": 2021, "14": 2022, "15": 2023, "16": 2024, "17": 2024,
    "18": 2023, "19": 2024, "20": 2019, "21": 2020, "22": 2026,
}

FIELDS = [
    "source_file", "source_group", "paper_title", "publication_year", "selected_label_column",
    "metric", "unit", "stored_transform", "direction", "better_means",
    "label_origin", "tier", "supervised_use", "valid_min", "valid_max",
    "censor_policy", "evidence", "confidence", "review_status", "notes",
    "document_filename", "filename_alias", "endpoint_definition",
    "raw_numeric_direction", "development_value_direction",
    "certification_label_source", "endpoint_grade", "affinity_grade",
    "grade_weight", "training_head", "primary_affinity_weight",
    "comparison_scope", "certification_notes", "certification_version",
]

CERTIFICATION_FIELDS = FIELDS[20:]


def group_number(source_group: str) -> str:
    return source_group.replace("\\", "/").rstrip("/").split("/")[-1]


def classify(row: dict[str, str]) -> dict[str, str]:
    source = row["source_file"].replace("\\", "/")
    name = Path(source).name.lower()
    group = group_number(row["source_group"])
    label = row.get("label_column", "")
    base = {
        "source_file": source,
        "source_group": row["source_group"],
        "paper_title": PAPERS[group],
        "publication_year": str(YEARS[group]),
        "selected_label_column": label,
        "metric": "",
        "unit": "",
        "stored_transform": "identity",
        "direction": "",
        "better_means": "",
        "label_origin": "experimental",
        "tier": "Gold",
        "supervised_use": "yes",
        "valid_min": "",
        "valid_max": "",
        "censor_policy": "keep",
        "evidence": "supplied paper plus original CSV measurement column",
        "confidence": "high",
        "review_status": "human_reviewed",
        "notes": "",
    }

    if group == "22":
        base.update(metric="none", direction="0", better_means="not_applicable",
                    label_origin="unlabeled", tier="Auxiliary", supervised_use="no",
                    censor_policy="not_applicable", confidence="high",
                    notes="evaluations is structured auxiliary metadata, not a directly supported numeric label")
    elif group in {"18", "19"} or "binary" in name:
        base.update(metric="binding_class", unit="0/1", direction="1",
                    better_means="1=binder", valid_min="0", valid_max="1",
                    censor_policy="reject_outside_range")
    elif group in {"3", "6"}:
        base.update(metric="predicted_log10_KD", unit="log10(nM)", direction="-1",
                    better_means="smaller predicted KD", label_origin="model_predicted",
                    tier="Weak", valid_min="-10", valid_max="20",
                    censor_policy="reject_nonfinite",
                    evidence="paper Fig. 1/2 identifies predicted affinity as log10 KD in nM; CSV values match",
                    notes="group 6 reproduces the labeled subset used to construct group 3")
    elif group == "4":
        base.update(metric="log10_KD_or_IC50", unit="log10(nM or source assay unit)",
                    direction="-1", better_means="smaller KD/IC50", tier="Silver",
                    valid_min="-12", valid_max="20", censor_policy="reject_nonfinite",
                    evidence="CSV log_Aff/fitness equals log10 affinity (e.g. 815 nM -> 2.9112); AbRank paper treats stronger binding as preferred",
                    notes="heterogeneous assays and units; compare only within compatible antigen/assay groups")
    elif group == "12":
        base.update(metric="binding_signal", unit="source-normalized signal", direction="1",
                    better_means="larger binding signal", tier="Silver",
                    censor_policy="reject_nonfinite",
                    notes="ANT/OVA binding is a relative assay signal, not an absolute KD")
    elif "ec50" in name or "ic50" in name:
        metric = "EC50" if "ec50" in name else "IC50"
        unit = "pM" if "adcc" in name else ("ng/uL" if group == "17" else "source unit")
        base.update(metric=metric, unit=unit, direction="-1",
                    better_means=f"smaller {metric}", valid_min="0", valid_max="",
                    censor_policy="require_positive_finite")
    elif group in {"5", "9", "16", "17"}:
        # Group 9's exported header says [M], but its paper and 3.3--2946.89
        # value range show that these MAGMA-seq values are in nM.
        unit = "M" if group in {"5", "17"} else "nM"
        base.update(metric="KD", unit=unit, direction="-1", better_means="smaller KD",
                    valid_min="0", valid_max="1" if unit == "M" else "1000000000",
                    censor_policy="require_positive_and_below_max",
                    notes=("exported header says M but paper/value scale is nM; " if group == "9" else "")
                    + "zero and physically implausible values are quarantined, not silently clipped")
    else:
        base.update(metric="negative_log10_KD", unit="-log10(M)", stored_transform="-log10(KD[M])",
                    direction="1", better_means="larger -log10(KD)", valid_min="-20", valid_max="30",
                    censor_policy="reject_nonfinite")
    return base


def load_certification(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {row["source_file"].replace("\\", "/"): row for row in rows}
    if len(result) != len(rows):
        raise ValueError("certification CSV contains duplicate source_file entries")
    return result


def apply_certification(
    registry: list[dict[str, str]],
    certification: dict[str, dict[str, str]],
) -> None:
    if not certification:
        return
    registry_files = {row["source_file"] for row in registry}
    if registry_files != set(certification):
        raise ValueError(
            "certification coverage mismatch: "
            f"missing={sorted(registry_files - set(certification))}, "
            f"extra={sorted(set(certification) - registry_files)}"
        )
    for row in registry:
        reviewed = certification[row["source_file"]]
        row.update({field: reviewed.get(field, "") for field in CERTIFICATION_FIELDS})
        head = row["training_head"]
        if head == "developability_ova_risk":
            row.update(
                metric="nonspecific_binding_signal",
                direction="-1",
                better_means="smaller OVA nonspecific-binding signal",
            )
        elif head == "mixed_endpoint_split_required":
            row.update(
                metric="mixed_endpoint_requires_split",
                direction="0",
                better_means="measurement_type_specific",
                supervised_use="conditional",
                censor_policy="split_by_measurement_type",
            )
        if group_number(row["source_group"]) in {"3", "6"}:
            row.update(
                label_origin="experimental_derived_model_calibrated",
                tier="Silver",
                evidence="AlphaSeq experimental measurements calibrated to log10(KD[nM])",
            )
        if "reviewed certification table" not in row["evidence"]:
            row["evidence"] = row["evidence"].rstrip("; ") + "; reviewed certification table"


def build(
    audit_csv: Path,
    output: Path,
    overrides: Path,
    certification_path: Path | None = None,
) -> None:
    with audit_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    registry = [classify(row) for row in rows]
    certification = load_certification(certification_path)
    apply_certification(registry, certification)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(registry)
    with overrides.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_file", "direction"])
        writer.writeheader()
        writer.writerows(
            {"source_file": row["source_file"], "direction": row["direction"]}
            for row in registry if row["direction"] in {"-1", "1"}
        )
    print(f"wrote {len(registry)} registry rows to {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=Path("data/processed/audit.csv"))
    parser.add_argument("--output", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument("--overrides", type=Path, default=Path("configs/direction_overrides.csv"))
    parser.add_argument(
        "--certification",
        type=Path,
        default=Path("configs/label_certification_revision.csv"),
    )
    args = parser.parse_args()
    build(args.audit, args.output, args.overrides, args.certification)


if __name__ == "__main__":
    main()
