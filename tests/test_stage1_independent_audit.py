import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_stage1 import audit_delimited, infer_roles
from scripts.build_stage1_label_registry import assay_from, registry_row
from scripts.build_label_registry import classify
from scripts.profile_stage1_labels import parse_number


class Stage1AuditTests(unittest.TestCase):
    def test_role_inference_is_candidate_only(self):
        roles = infer_roles(["heavy", "light", "antigen_seq", "KD (nM)", "fitness"])
        self.assertEqual(roles["heavy"], ["heavy"])
        self.assertEqual(roles["light"], ["light"])
        self.assertEqual(roles["antigen"], ["antigen_seq"])
        self.assertIn("KD (nM)", roles["label"])
        self.assertEqual(infer_roles(["sequence", "evaluations"])["heavy"], ["sequence"])
        self.assertEqual(infer_roles(["LC", "light"])["light"], ["light"])

    def test_preamble_and_bad_width_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "example.csv"
            source.write_text(
                "release statement,,,\nheavy,light,KD (nM),fitness\nAAAA,CCCC,1,9\nBBBB,,2\n",
                encoding="utf-8",
            )
            result = audit_delimited(source, root, 10)
            self.assertEqual(result.header_row, 2)
            self.assertEqual(result.row_count, 2)
            self.assertEqual(result.bad_width_rows, 1)
            self.assertIn("preamble_rows_skipped:1", result.notes)

    def test_cli_refuses_output_below_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/audit_stage1.py"), "--data-root", str(data),
                 "--output-json", str(data / "bad.json"), "--output-csv", str(root / "ok.csv")],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((data / "bad.json").exists())

    def test_registry_keeps_semantics_pending(self):
        record = {
            "path": "初赛-序列数据/1/example_kd.csv", "sheet": "", "format": "csv",
            "label_candidates": ["KD (nM)", "fitness"],
        }
        row = registry_row(record, 1)
        self.assertEqual(row["proposed_label_column"], "fitness")
        self.assertEqual(row["proposed_direction"], "higher_is_better")
        self.assertEqual(row["review_status"], "pending_review")
        self.assertEqual(row["quality_tier"], "pending_review")

    def test_binary_is_auxiliary(self):
        self.assertEqual(assay_from("x_binary.csv", ["fitness"]), "binary_binding")

    def test_main_registry_excludes_binary_from_ranking_supervision(self):
        row = classify({
            "source_file": "初赛-序列数据/18/example_binary.csv",
            "source_group": "初赛-序列数据/18",
            "label_column": "fitness",
        })
        self.assertEqual(row["tier"], "Auxiliary")
        self.assertEqual(row["supervised_use"], "no")

    def test_censored_values_are_not_silently_numeric(self):
        self.assertEqual(parse_number("1.2e-9"), (1.2e-9, False))
        self.assertEqual(parse_number("<1e-12"), (None, True))
        self.assertEqual(parse_number("not measured"), (None, False))


if __name__ == "__main__":
    unittest.main()
