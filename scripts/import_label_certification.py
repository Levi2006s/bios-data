"""Import the reviewed label-certification table from a DOCX file.

The importer uses only the Python standard library.  It extracts the ten-column
tables, matches each document filename to the audited registry, and writes a
machine-readable CSV that can be merged by ``build_label_registry.py``.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADERS = [
    "来源",
    "文件名",
    "终点/标签定义",
    "原始数值方向",
    "开发价值方向",
    "标签来源",
    "原终点等级",
    "亲和力等级",
    "可比范围",
    "认证意见/处理",
]
GRADE_WEIGHTS = {
    "A": 1.0,
    "A/B": 0.875,
    "B": 0.75,
    "B/C": 0.625,
    "C": 0.5,
    "C/D": 0.25,
    "D": 0.0,
    "NA": 0.0,
}
OUTPUT_FIELDS = [
    "source_file",
    "document_filename",
    "filename_alias",
    "endpoint_definition",
    "raw_numeric_direction",
    "development_value_direction",
    "certification_label_source",
    "endpoint_grade",
    "affinity_grade",
    "grade_weight",
    "training_head",
    "primary_affinity_weight",
    "comparison_scope",
    "certification_notes",
    "certification_version",
]


def _visible_text(node: ET.Element) -> str:
    pieces: list[str] = []
    for element in node.iter():
        if element.tag == W + "t":
            pieces.append(element.text or "")
        elif element.tag == W + "tab":
            pieces.append("\t")
        elif element.tag == W + "br":
            pieces.append("\n")
    return "".join(pieces).strip()


def _normalise_filename(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _table_rows(docx_path: Path) -> list[list[str]]:
    with zipfile.ZipFile(docx_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    rows: list[list[str]] = []
    for table in root.iter(W + "tbl"):
        table_rows: list[list[str]] = []
        for row in table.findall(W + "tr"):
            table_rows.append([_visible_text(cell) for cell in row.findall(W + "tc")])
        if table_rows and table_rows[0] == HEADERS:
            rows.extend(item for item in table_rows[1:] if len(item) == len(HEADERS))
    return rows


def _training_head(source_group: str, filename: str, endpoint: str) -> str:
    text = f"{filename} {endpoint}".casefold()
    if source_group == "22" or "无监督" in text:
        return "unsupervised"
    if source_group == "4" or "混合 kd" in text:
        return "mixed_endpoint_split_required"
    if "adcc" in text:
        return "adcc_function"
    if "bind/no-bind" in text or "binary" in text:
        return "binding_classification"
    if "ova" in text:
        return "developability_ova_risk"
    if "ic50" in text:
        return "neutralization_ic50"
    if "ec50" in text:
        return "binding_ec50"
    if "相对结合信号" in text:
        return "relative_target_binding"
    return "affinity_kd"


def _match_source(
    source_group: str,
    document_filename: str,
    registry_by_group: dict[str, dict[str, str]],
) -> tuple[str, str]:
    candidates = registry_by_group.get(source_group, {})
    key = _normalise_filename(document_filename)
    if key in candidates:
        return candidates[key], ""
    ranked = sorted(
        (
            (difflib.SequenceMatcher(None, key, candidate).ratio(), candidate)
            for candidate in candidates
        ),
        reverse=True,
    )
    close = [item for item in ranked if item[0] >= 0.90]
    if not close or (len(close) > 1 and close[0][0] - close[1][0] < 0.01):
        raise ValueError(
            f"Cannot uniquely match source {source_group}, file {document_filename!r}; "
            f"candidates={close}"
        )
    source_file = candidates[close[0][1]]
    return source_file, Path(source_file).name


def import_certification(
    docx_path: Path,
    registry_path: Path,
    output_path: Path,
    *,
    version: str,
) -> dict[str, object]:
    with registry_path.open("r", encoding="utf-8-sig", newline="") as handle:
        registry = list(csv.DictReader(handle))
    registry_by_group: dict[str, dict[str, str]] = {}
    for row in registry:
        group = row["source_group"].replace("\\", "/").rstrip("/").split("/")[-1]
        registry_by_group.setdefault(group, {})[_normalise_filename(Path(row["source_file"]).name)] = row[
            "source_file"
        ]

    document_rows = _table_rows(docx_path)
    output_rows: list[dict[str, str]] = []
    for cells in document_rows:
        (
            source_group,
            document_filename,
            endpoint,
            raw_direction,
            development_direction,
            label_source,
            endpoint_grade,
            affinity_grade,
            comparison_scope,
            notes,
        ) = cells
        if affinity_grade not in GRADE_WEIGHTS:
            raise ValueError(f"Unknown affinity grade {affinity_grade!r} in {document_filename}")
        source_file, alias = _match_source(source_group, document_filename, registry_by_group)
        training_head = _training_head(source_group, document_filename, endpoint)
        grade_weight = GRADE_WEIGHTS[affinity_grade]
        primary_weight = grade_weight if training_head == "affinity_kd" else 0.0
        output_rows.append(
            {
                "source_file": source_file,
                "document_filename": document_filename,
                "filename_alias": alias,
                "endpoint_definition": endpoint,
                "raw_numeric_direction": raw_direction,
                "development_value_direction": development_direction,
                "certification_label_source": label_source,
                "endpoint_grade": endpoint_grade,
                "affinity_grade": affinity_grade,
                "grade_weight": f"{grade_weight:.12g}",
                "training_head": training_head,
                "primary_affinity_weight": f"{primary_weight:.12g}",
                "comparison_scope": comparison_scope,
                "certification_notes": notes,
                "certification_version": version,
            }
        )

    source_files = [row["source_file"] for row in output_rows]
    if len(source_files) != len(set(source_files)):
        duplicates = [name for name, count in Counter(source_files).items() if count > 1]
        raise ValueError(f"Certification has duplicate matched files: {duplicates}")
    registry_files = {row["source_file"] for row in registry}
    missing = sorted(registry_files - set(source_files))
    extra = sorted(set(source_files) - registry_files)
    if missing or extra:
        raise ValueError(f"Certification coverage mismatch: missing={missing}, extra={extra}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    return {
        "document_rows": len(document_rows),
        "registry_rows": len(registry),
        "matched_rows": len(output_rows),
        "filename_aliases": sum(bool(row["filename_alias"]) for row in output_rows),
        "affinity_grade_counts": dict(Counter(row["affinity_grade"] for row in output_rows)),
        "training_head_counts": dict(Counter(row["training_head"] for row in output_rows)),
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a reviewed DOCX label-certification table.")
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path("configs/label_registry.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("configs/label_certification_revision.csv")
    )
    parser.add_argument("--version", default="2026-08-03_docx_revision")
    args = parser.parse_args()
    report = import_certification(
        args.docx, args.registry, args.output, version=args.version
    )
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
