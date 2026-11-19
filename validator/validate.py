#!/usr/bin/env python3
"""Validator của nhóm VoDuyThanh — Day 10.

    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Chỉ đọc thư mục delivery được truyền vào. Chỉ thư viện chuẩn (+ scripts/pngutil.py). Không mạng.
Không đọc _private/, data_source/, annotation COCO. Không nhúng tên ảnh/đáp án của seed nào.

Cấu trúc (mỗi nhóm luật một hàm, mỗi hàm trả về list lỗi {"type", "target"}):
  - check_file_rules      (Người 1) missing_image, wrong_hash
  - check_meta_rules      (Người 1) scene_leak, guideline_mismatch
  - check_label_rules     (Người 2) invalid_class, bbox_out_of_bounds, duplicate_box
  - check_panoptic_rules  (Người 2) invalid_category_id, thing_overlap
  - cross_check           (Người 3, 4) ứng viên gán nhãn -> candidates.json (không vào errors.json)

errors.json chỉ chứa lỗi luật. Lỗi gán nhãn đi qua review_log.csv rồi scripts/merge_review.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

# pngutil.py (thư viện chuẩn) nằm ở scripts/ cạnh validator/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


# ---------------------------------------------------------------- đọc lô

class Delivery:
    """Mọi thứ validator cần, đọc một lần từ thư mục delivery."""

    def __init__(self, root: Path):
        self.root = root
        man = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.items: dict[str, dict] = man["items"]  # stem -> {image, label, mask, *_sha256}
        meta = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        self.meta: dict[str, dict] = {m["image"]: m for m in meta["items"]}
        with (root / "jobs.csv").open(encoding="utf-8", newline="") as f:
            self.jobs: dict[str, dict] = {row["job_id"].strip(): row for row in csv.DictReader(f)}
        self.classes: dict[int, str] = {}
        for line in (root / "classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                cid, name = line.split(" ", 1)
                self.classes[int(cid)] = name.strip()
        pan = json.loads((root / "panoptic.json").read_text(encoding="utf-8"))
        self.categories: dict[int, dict] = {c["id"]: c for c in pan["categories"]}
        # Ghép ảnh panoptic theo tên file (không đuôi), vì đề ẩn đổi tên ảnh và id.
        self.pan_images: dict[str, dict] = {Path(im["file_name"]).stem: im for im in pan["images"]}
        self.pan_anns: dict[str, dict] = {Path(a["file_name"]).stem: a for a in pan["annotations"]}

    def path(self, stem: str, kind: str) -> Path:
        """kind = image | label | mask, theo đường dẫn ghi trong manifest."""
        return self.root / self.items[stem][kind]

    def size(self, stem: str) -> tuple[int, int] | None:
        im = self.pan_images.get(stem)
        return (im["width"], im["height"]) if im else None

    def read_boxes(self, stem: str) -> list[tuple[int, float, float, float, float]]:
        """Nhãn YOLO: (class_id, xc, yc, w, h) chuẩn hoá 0-1. Dòng hỏng bị bỏ qua."""
        p = self.path(stem, "label")
        out = []
        if not p.is_file():
            return out
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                out.append((int(float(parts[0])), *(float(v) for v in parts[1:5])))
            except ValueError:
                continue
        return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:  # bytes, không phải text
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- Người 1: luật mức file + metadata

def check_file_rules(d: Delivery) -> tuple[list[dict], set[str]]:
    """missing_image: manifest có ảnh mà thiếu file.
    wrong_hash: sha256 tự tính trên bytes của ảnh khác sha256 ghi trong manifest.
    Trả về (lỗi, tập ảnh thiếu file) để các luật sau bỏ qua ảnh không đọc được."""
    errors, missing = [], set()
    for stem, it in sorted(d.items.items()):
        img = d.path(stem, "image")
        if not img.is_file():
            errors.append({"type": "missing_image", "target": stem})
            missing.add(stem)
            continue
        if sha256_file(img) != it.get("image_sha256", "").lower():
            errors.append({"type": "wrong_hash", "target": stem})
    return errors, missing


def check_meta_rules(d: Delivery) -> list[dict]:
    """scene_leak: một cảnh có ảnh ở nhiều split -> target là scene_id.
    guideline_mismatch: guideline_version của ảnh khác guideline ghi ở job của nó (jobs.csv)."""
    errors = []
    splits: dict[str, set[str]] = {}
    for stem in sorted(d.items):
        m = d.meta.get(stem)
        if not m:
            continue
        splits.setdefault(m["scene_id"], set()).add(m["split"].strip())
        job = d.jobs.get(m["job_id"].strip())
        if job and m["guideline_version"].strip() != job["guideline"].strip():
            errors.append({"type": "guideline_mismatch", "target": stem})
    for scene, s in sorted(splits.items()):
        if len(s) > 1:
            errors.append({"type": "scene_leak", "target": scene})
    return errors


# ---------------------------------------------------------------- Người 2: luật nhãn detection + panoptic

def check_label_rules(d: Delivery, skip: set[str]) -> list[dict]:
    """TODO (Người 2): invalid_class, bbox_out_of_bounds, duplicate_box.
    Gợi ý: d.read_boxes(stem), d.size(stem); duplicate_box = cùng lớp, cùng kích thước, lệch tâm 1–2 px."""
    return []


def check_panoptic_rules(d: Delivery, skip: set[str]) -> list[dict]:
    """TODO (Người 2): invalid_category_id, thing_overlap.
    Gợi ý: d.categories, d.pan_anns[stem]["segments_info"]; đọc mask bằng pngutil (id = R + G*256 + B*256^2)."""
    return []


# ---------------------------------------------------------------- Người 3, 4: đối chiếu det <-> panoptic

def cross_check(d: Delivery, skip: set[str]) -> list[dict]:
    """TODO (Người 3, 4): ứng viên class_swap, category_swap, missing_box, bbox_drift, instance_merge.
    Mỗi ứng viên: {"image", "type", "reason", ...}. Không đưa vào errors.json; phải xem ảnh trước."""
    return []


# ---------------------------------------------------------------- main

def one_fault_per_image(errors: list[dict]) -> list[dict]:
    """Mỗi ảnh mang nhiều nhất một lỗi: giữ lỗi đầu tiên theo thứ tự luật đã chạy."""
    seen, out = set(), []
    for e in errors:
        key = e["target"] if e["type"] != "scene_leak" else ("scene", e["target"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def validate(root: Path) -> tuple[list[dict], list[dict]]:
    d = Delivery(root)
    file_errors, missing = check_file_rules(d)
    errors = file_errors + check_meta_rules(d)
    errors += check_label_rules(d, missing)
    errors += check_panoptic_rules(d, missing)
    errors = one_fault_per_image(errors)
    candidates = cross_check(d, missing)
    return errors, candidates


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lô Day 10 (nhóm VoDuyThanh)")
    ap.add_argument("delivery", help="thư mục delivery/")
    ap.add_argument("--out", required=True, help="errors.json (lỗi luật)")
    ap.add_argument("--candidates", help="candidates.json (ứng viên lỗi gán nhãn, cần xem ảnh)")
    args = ap.parse_args()
    root = Path(args.delivery)
    if not (root / "manifest.json").is_file():
        raise SystemExit(f"Không thấy {root / 'manifest.json'}: đường dẫn delivery sai?")
    errors, candidates = validate(root)
    errors.sort(key=lambda e: (e["type"], e["target"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for e in errors:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    print(f"{len(errors)} lỗi luật -> {out}  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if args.candidates:
        c = Path(args.candidates)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{len(candidates)} ứng viên gán nhãn -> {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
