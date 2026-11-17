import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402
import score_findings  # noqa: E402


def write_source(root: Path, n: int = 24) -> None:
    images = root / "images" / "train2017"
    labels = root / "labels" / "train2017"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)
    for i in range(n):
        stem = f"img_{i:04d}"
        (images / f"{stem}.jpg").write_bytes(b"\xff\xd8" + stem.encode() + b"\xff\xd9")
        (labels / f"{stem}.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=True, cwd=ROOT)


class MetricsTest(unittest.TestCase):
    def test_empty_truth_and_prediction_is_perfect(self):
        row = metrics.score(set(), set())
        self.assertEqual(row["precision"], 1.0)
        self.assertEqual(row["recall"], 1.0)

    def test_empty_truth_does_not_change_rank(self):
        reports = [
            {"task": "detection", "truth_count": 8, "score": {"groups": {"reference_or_review": {"recall": 0.5}}}},
            {"task": "panoptic", "truth_count": 8, "score": {"groups": {"reference_or_review": {"recall": 0.25}}}},
            {"task": "detection", "truth_count": 0, "score": {"groups": {"reference_or_review": {"recall": 1.0}}}},
            {"task": "panoptic", "truth_count": 0, "score": {"groups": {"reference_or_review": {"recall": 1.0}}}},
        ]
        self.assertIn("0.375", score_findings.rank_line(reports))

    def test_hold_ignores_semantic_only_findings(self):
        self.assertEqual(metrics.decision([{"type": "class_swap", "target": "a"}]), "HOLD")
        self.assertEqual(metrics.decision([{"type": "scene_leak", "target": "simulated_group_000"}]), "HOLD")


class PipelineTest(unittest.TestCase):
    def test_open_seed_splits_rule_and_semantic(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / "source"
            write_source(source)
            faulty = tmp / "s11"
            clean = tmp / "clean"
            run("inject_faults.py", "--source", str(source), "--seed", "11", "--fault-count", "8", "--out", str(faulty), "--dev-truth")
            truth = json.loads((faulty / "_private" / "truth.json").read_text(encoding="utf-8"))["errors"]
            rule_only = [
                {"type": item["type"], "target": item["target"]}
                for item in truth
                if item["type"] not in {"bbox_drift", "class_swap"}
            ]
            (faulty / "errors.json").write_text(json.dumps({"errors": rule_only}), encoding="utf-8")
            run("score_findings.py", "--run", str(faulty))
            report = json.loads((faulty / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(report["decision"], "HOLD")
            groups = report["score"]["groups"]
            self.assertEqual(groups["rule_detectable"]["recall"], 1.0)
            self.assertEqual(groups["reference_or_review"]["recall"], 0.0)
            self.assertEqual(groups["reference_or_review"]["fp"], 0)
            self.assertIsNone(groups["reference_or_review"]["precision"])
            self.assertTrue((faulty / "report.md").is_file())

            run("inject_faults.py", "--source", str(source), "--seed", "44", "--fault-count", "0", "--out", str(clean), "--dev-truth")
            (clean / "errors.json").write_text(json.dumps({"errors": []}), encoding="utf-8")
            run("score_findings.py", "--run", str(clean))
            clean_report = json.loads((clean / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(clean_report["decision"], "RELEASE_CANDIDATE")
            self.assertEqual(clean_report["error_count"], 0)

            lineage_root = tmp / "runs"
            release_id = "coco500_test"
            run("lineage.py", "--root", str(lineage_root), "record", "--event", "decision", "--release-id", release_id, "--decision", "HOLD")
            run("lineage.py", "--root", str(lineage_root), "record", "--event", "train", "--release-id", release_id, "--run-id", "R-021")
            shown = subprocess.run(
                [sys.executable, str(SCRIPTS / "lineage.py"), "--root", str(lineage_root), "impact", "--release-id", release_id],
                check=True, capture_output=True, text=True,
            )
            self.assertIn("R-021: affected=True", shown.stdout)


class PanopticTest(unittest.TestCase):
    def test_label_faults_match_ground_truth_and_hide_from_structure_check(self):
        import pngutil

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            (source / "images").mkdir(parents=True)
            (source / "masks").mkdir()
            images = [
                {"id": 1, "file_name": "000000000001.jpg", "width": 4, "height": 2},
                {"id": 2, "file_name": "000000000002.jpg", "width": 4, "height": 2},
                {"id": 3, "file_name": "000000000003.jpg", "width": 4, "height": 2},
                {"id": 4, "file_name": "000000000004.jpg", "width": 4, "height": 2},
            ]
            masks = {
                1: [10, 10, 11, 11, 10, 10, 11, 11],
                2: [20, 20, 21, 21, 20, 20, 21, 21],
                3: [12] * 8,
                4: [13] * 8,
            }
            annotations = [
                {"image_id": 1, "file_name": "000000000001.png", "segments_info": [
                    {"id": 10, "category_id": 1, "iscrowd": 0, "area": 4, "bbox": [0, 0, 2, 2]},
                    {"id": 11, "category_id": 1, "iscrowd": 0, "area": 4, "bbox": [2, 0, 2, 2]},
                ]},
                {"image_id": 2, "file_name": "000000000002.png", "segments_info": [
                    {"id": 20, "category_id": 1, "iscrowd": 0, "area": 4, "bbox": [0, 0, 2, 2]},
                    {"id": 21, "category_id": 2, "iscrowd": 0, "area": 4, "bbox": [2, 0, 2, 2]},
                ]},
                {"image_id": 3, "file_name": "000000000003.png", "segments_info": [
                    {"id": 12, "category_id": 1, "iscrowd": 0, "area": 8, "bbox": [0, 0, 4, 2]},
                ]},
                {"image_id": 4, "file_name": "000000000004.png", "segments_info": [
                    {"id": 13, "category_id": 1, "iscrowd": 0, "area": 8, "bbox": [0, 0, 4, 2]},
                ]},
            ]
            for image in images:
                (source / "images" / image["file_name"]).write_bytes(b"jpg")
                raw = bytearray()
                for segment in masks[image["id"]]:
                    raw += bytes(pngutil.segment_rgb(segment))
                pngutil.write_rgb(source / "masks" / f"{Path(image['file_name']).stem}.png", 4, 2, raw)
            document = {
                "categories": [
                    {"id": 1, "name": "person", "isthing": 1},
                    {"id": 2, "name": "bicycle", "isthing": 1},
                ],
                "images": images,
                "annotations": annotations,
            }
            (source / "panoptic.json").write_text(json.dumps(document), encoding="utf-8")
            out = Path(tmp) / "p11"
            run("inject_panoptic.py", "--source", str(source), "--seed", "11", "--fault-count", "4", "--out", str(out))
            truth = json.loads((out / "_private" / "truth.json").read_text(encoding="utf-8"))["errors"]
            self.assertEqual(
                sorted(item["type"] for item in truth),
                ["category_swap", "instance_merge", "invalid_category_id", "thing_overlap"],
            )
            released = json.loads((out / "delivery" / "panoptic.json").read_text(encoding="utf-8"))
            by_stem = {Path(ann["file_name"]).stem: ann for ann in released["annotations"]}
            merged_stem = next(item["target"] for item in truth if item["type"] == "instance_merge")
            self.assertEqual(len(by_stem[merged_stem]["segments_info"]), 1)
            invalid_stem = next(item["target"] for item in truth if item["type"] == "invalid_category_id")
            self.assertIn(9999, [segment["category_id"] for segment in by_stem[invalid_stem]["segments_info"]])
            overlap = next(item for item in truth if item["type"] == "thing_overlap")
            width, _, pixels = pngutil.read_rgb(out / "delivery" / "masks" / f"{overlap['target']}.png")
            donor = next(segment for segment in by_stem[overlap["target"]]["segments_info"] if segment["id"] == overlap["donor_segment_id"])
            counted = sum(1 for index in range(0, len(pixels), 3) if pngutil.segment_id(pixels, index) == donor["id"])
            self.assertLess(counted, donor["area"])
            submitted = [{"type": "invalid_category_id", "target": invalid_stem}]
            (out / "errors.json").write_text(json.dumps({"errors": submitted}), encoding="utf-8")
            run("score_findings.py", "--run", str(out))
            report = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(report["score"]["overall"]["recall"], 0.25)
            perfect = metrics.score(metrics.pairs(truth), metrics.pairs(truth))
            self.assertEqual(perfect["recall"], 1.0)
            self.assertEqual(perfect["precision"], 1.0)

    def test_real_coco_mask_ids_match_json(self):
        import pngutil

        root = ROOT / "data_source" / "coco_panoptic500"
        if not (root / "panoptic.json").is_file():
            self.skipTest("coco panoptic not downloaded")
        document = json.loads((root / "panoptic.json").read_text(encoding="utf-8"))
        annotation = document["annotations"][0]
        width, height, pixels = pngutil.read_rgb(root / "masks" / annotation["file_name"])
        image = next(image for image in document["images"] if image["id"] == annotation["image_id"])
        self.assertEqual((width, height), (image["width"], image["height"]))
        present = {pngutil.segment_id(pixels, index) for index in range(0, len(pixels), 3)} - {0}
        declared = {segment["id"] for segment in annotation["segments_info"]}
        self.assertTrue(declared <= present)


if __name__ == "__main__":
    unittest.main()
