#!/usr/bin/env python3
"""Validator của nhóm 57 — Day 10.

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
from array import array
from pathlib import Path

# pngutil.py (thư viện chuẩn) nằm ở scripts/ cạnh validator/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rules import label_rules as lr  # noqa: E402  (Người 2: luật nhãn detection)
from rules import panoptic_rules as pr  # noqa: E402  (Người 2: luật panoptic)
from rules import drift_merge as dm  # noqa: E402  (Người 4: bbox_drift, instance_merge)


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
    """(Người 2) invalid_class, bbox_out_of_bounds, duplicate_box. Từng luật nằm ở rules/label_rules.py."""
    class_ids = set(d.classes)
    errors = []
    for stem in sorted(d.items):
        if stem in skip:
            continue
        boxes = d.read_boxes(stem)
        if lr.has_invalid_class(boxes, class_ids):
            errors.append({"type": "invalid_class", "target": stem})
        elif lr.has_out_of_bounds(boxes):
            errors.append({"type": "bbox_out_of_bounds", "target": stem})
        else:
            size = d.size(stem)
            if size and lr.has_duplicate_box(boxes, *size):
                errors.append({"type": "duplicate_box", "target": stem})
    return errors


def check_panoptic_rules(d: Delivery, skip: set[str]) -> list[dict]:
    """(Người 2) invalid_category_id, thing_overlap. Từng luật nằm ở rules/panoptic_rules.py."""
    category_ids = set(d.categories)
    errors = []
    for stem in sorted(d.items):
        ann = d.pan_anns.get(stem)
        if stem in skip or ann is None:
            continue
        segments = ann["segments_info"]
        mask = d.path(stem, "mask")
        if pr.has_invalid_category(segments, category_ids):
            errors.append({"type": "invalid_category_id", "target": stem})
        elif mask.is_file() and pr.has_thing_overlap(segments, mask):
            errors.append({"type": "thing_overlap", "target": stem})
    return errors


# ---------------------------------------------------------------- Người 3, 4: đối chiếu det <-> panoptic

# ---- Người 3 (Nguyễn Hoài Nam): ghép box <-> segment theo tên lớp + pixel mask;
#      ứng viên class_swap/category_swap, missing_box. Người 4 dùng lại match() cho bbox_drift, instance_merge.

# ---------------------------------------------------------------- ngưỡng (chỉnh sau khi đo lô sạch)

# Ghép cùng lớp: một cặp được coi là cùng một vật khi
MATCH_MIN_IOU = 0.30      # IoU giữa box detection và bbox của segment
MATCH_MIN_COVER = 0.50    # tỉ lệ pixel của segment nằm trong box

# Lệch lớp (class_swap / category_swap): box và segment KHÁC tên lớp nhưng trùng vị trí rất chặt
SWAP_MIN_IOU = 0.70
SWAP_MIN_COVER = 0.85

# missing_box: segment thing không có box nào cùng lớp
MISSING_MIN_AREA_FRAC = 0.005  # segment phải chiếm >= 0,5% diện tích ảnh (vật "đáng kể"); lô sạch vẫn 0 ứng viên ở 0,2%–1%
MISSING_MAX_COVER = 0.30       # không box cùng lớp nào chứa quá 30% pixel của segment


# ---------------------------------------------------------------- 1. box YOLO -> pixel

def box_to_px(xc: float, yc: float, w: float, h: float, W: int, H: int) -> tuple[int, int, int, int]:
    """(x1, y1, x2, y2) pixel, x2/y2 không tính (kiểu slice), đã cắt trong ảnh."""
    x1 = round((xc - w / 2) * W)
    y1 = round((yc - h / 2) * H)
    x2 = round((xc + w / 2) * W)
    y2 = round((yc + h / 2) * H)
    return max(0, x1), max(0, y1), min(W, x2), min(H, y2)


def iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


# ---------------------------------------------------------------- 2. đọc mask

def read_segment_ids(mask_path: Path) -> tuple[int, int, array]:
    """Trả về (W, H, ids) với ids[y*W + x] = id segment của pixel đó.

    Ghép R, G, B thành số 32-bit bằng slice của bytearray (chạy ở tốc độ C),
    không lặp từng pixel trong Python."""
    import pngutil

    W, H, rgb = pngutil.read_rgb(mask_path)
    buf = bytearray(W * H * 4)
    buf[0::4] = rgb[0::3]
    buf[1::4] = rgb[1::3]
    buf[2::4] = rgb[2::3]
    ids = array("I")
    if ids.itemsize != 4:  # máy hiếm gặp: 'I' không phải 4 byte
        ids = array("L")
    ids.frombytes(bytes(buf))
    if sys.byteorder == "big":
        ids.byteswap()
    return W, H, ids


def count_in_box(ids: array, W: int, box: tuple[int, int, int, int], seg_id: int) -> int:
    """Số pixel của seg_id nằm trong box."""
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return 0
    n = 0
    for y in range(y1, y2):
        n += ids[y * W + x1 : y * W + x2].count(seg_id)
    return n


# ---------------------------------------------------------------- 3. ghép

def load_image(d, stem: str):
    """Gom dữ liệu một ảnh. Trả None nếu thiếu nhãn, mask hoặc annotation."""
    ann = d.pan_anns.get(stem)
    size = d.size(stem)
    if ann is None or size is None:
        return None
    mask_path = d.path(stem, "mask")
    if not mask_path.is_file():
        return None
    W, H, ids = read_segment_ids(mask_path)

    boxes = []  # (idx, tên lớp, box pixel)
    for i, (cid, xc, yc, w, h) in enumerate(d.read_boxes(stem)):
        name = d.classes.get(cid)
        if name is None:  # invalid_class: luật của Người 2 lo
            continue
        b = box_to_px(xc, yc, w, h, W, H)
        if b[2] > b[0] and b[3] > b[1]:
            boxes.append((i, name, b))

    segs = {}  # id -> {name, bbox, pixels}
    for s in ann.get("segments_info", []):
        cat = d.categories.get(s["category_id"])
        if cat is None or not cat.get("isthing") or s.get("iscrowd"):
            continue  # stuff, crowd, hoặc invalid_category_id: không ghép
        x, y, w, h = s["bbox"]
        pixels = ids.count(s["id"])  # đếm thật, không tin "area" (có thể là thing_overlap)
        if pixels == 0:
            continue
        segs[s["id"]] = {
            "name": cat["name"],
            "bbox": (int(x), int(y), int(round(x + w)), int(round(y + h))),
            "pixels": pixels,
        }
    return {"W": W, "H": H, "ids": ids, "boxes": boxes, "segs": segs}


def match(img: dict) -> dict:
    """Ghép một-một box <-> segment.

    Lượt 1: cùng tên lớp, điểm = IoU * cover, ngưỡng lỏng (box hơi lệch vẫn ghép được để Người 4 xét drift).
    Lượt 2: box và segment còn lẻ, KHÁC tên lớp, trùng vị trí rất chặt -> cặp lệch lớp.

    cover = pixel của segment nằm trong box / tổng pixel segment
    fill  = pixel của segment nằm trong box / diện tích box
    """
    ids, W = img["ids"], img["W"]
    inside: dict[tuple[int, int], int] = {}
    stats = []  # (score, box_idx, seg_id, iou, cover, fill, same_class)
    for bi, bname, b in img["boxes"]:
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        for sid, s in img["segs"].items():
            o = iou(b, s["bbox"])
            if o == 0:
                continue
            n = count_in_box(ids, W, b, sid)
            inside[(bi, sid)] = n
            cover = n / s["pixels"]
            fill = n / area_b
            stats.append((o * cover, bi, sid, o, cover, fill, bname == s["name"]))

    box_by_idx = {bi: (bname, b) for bi, bname, b in img["boxes"]}
    used_b, used_s, pairs, swaps = set(), set(), [], []

    for score, bi, sid, o, cover, fill, same in sorted(stats, reverse=True):
        if not same or bi in used_b or sid in used_s:
            continue
        if o >= MATCH_MIN_IOU and cover >= MATCH_MIN_COVER:
            used_b.add(bi)
            used_s.add(sid)
            pairs.append({"box_idx": bi, "seg_id": sid, "cls": box_by_idx[bi][0],
                          "iou": round(o, 3), "cover": round(cover, 3), "fill": round(fill, 3)})

    for score, bi, sid, o, cover, fill, same in sorted(stats, reverse=True):
        if same or bi in used_b or sid in used_s:
            continue
        if o >= SWAP_MIN_IOU and cover >= SWAP_MIN_COVER:
            used_b.add(bi)
            used_s.add(sid)
            swaps.append({"box_idx": bi, "seg_id": sid, "det_class": box_by_idx[bi][0],
                          "pan_class": img["segs"][sid]["name"], "iou": round(o, 3), "cover": round(cover, 3)})

    return {
        "pairs": pairs,
        "swaps": swaps,
        "unmatched_boxes": [bi for bi, _, _ in img["boxes"] if bi not in used_b],
        "unmatched_segs": [sid for sid in img["segs"] if sid not in used_s],
        "inside": inside,
    }


# ---------------------------------------------------------------- 4. ứng viên

def mismatch_candidates(stem: str, img: dict, m: dict) -> list[dict]:
    out = []
    for p in m["swaps"]:
        _, _, b = next(x for x in img["boxes"] if x[0] == p["box_idx"])
        out.append({
            "image": stem,
            "type": "class_swap|category_swap",
            "reason": f"box #{p['box_idx']} detection ghi '{p['det_class']}', segment {p['seg_id']} panoptic ghi "
                      f"'{p['pan_class']}', trùng vị trí (IoU {p['iou']}, {int(p['cover'] * 100)}% pixel trong box). "
                      f"Mở ảnh: vật thật là gì? detection sai -> class_swap, panoptic sai -> category_swap",
            "box_px": list(b),
            "seg_id": p["seg_id"],
            "det_class": p["det_class"],
            "pan_class": p["pan_class"],
        })
    return out


def missing_box_candidates(stem: str, img: dict, m: dict) -> list[dict]:
    out = []
    min_px = MISSING_MIN_AREA_FRAC * img["W"] * img["H"]
    for sid in m["unmatched_segs"]:
        s = img["segs"][sid]
        if s["pixels"] < min_px:
            continue
        best = 0.0
        for bi, bname, _ in img["boxes"]:
            if bname == s["name"]:
                best = max(best, m["inside"].get((bi, sid), 0) / s["pixels"])
        if best > MISSING_MAX_COVER:
            continue  # có box cùng lớp phủ một phần: nghiêng về bbox_drift (Người 4), không phải thiếu box
        out.append({
            "image": stem,
            "type": "missing_box",
            "reason": f"segment {sid} '{s['name']}' chiếm {s['pixels']} px "
                      f"({100 * s['pixels'] / (img['W'] * img['H']):.1f}% ảnh), không box '{s['name']}' nào phủ "
                      f"(cao nhất {int(best * 100)}%). Mở ảnh: vật có rõ không, có bị che/cắt không?",
            "seg_bbox_px": list(s["bbox"]),
            "seg_id": sid,
            "pan_class": s["name"],
        })
    return out


def cross_candidates_n3(d, skip: set[str]) -> tuple[list[dict], dict]:
    """Chạy cho cả lô. Trả về (ứng viên của Người 3, {stem: (img, match)} để Người 4 dùng lại)."""
    cands, cache = [], {}
    for stem in sorted(d.items):
        if stem in skip:
            continue
        img = load_image(d, stem)
        if img is None:
            continue
        m = match(img)
        cache[stem] = (img, m)
        cands += mismatch_candidates(stem, img, m)
        cands += missing_box_candidates(stem, img, m)
    return cands, cache


def cross_check(d: Delivery, skip: set[str]) -> list[dict]:
    """Ứng viên class_swap, category_swap, missing_box (Người 3), bbox_drift, instance_merge (Người 4).
    Mỗi ứng viên: {"image", "type", "reason", ...}. Không đưa vào errors.json; phải xem ảnh trước."""
    candidates, cache = cross_candidates_n3(d, skip)
    candidates += dm.drift_merge_candidates(cache)  # Người 4: rules/drift_merge.py
    return candidates


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
    # Mỗi ảnh mang nhiều nhất một lỗi (DELIVERY mục 2): ảnh đã có lỗi luật thì không sinh ứng viên gán nhãn.
    # Ví dụ: ảnh duplicate_box có hai box cùng lớp chứa trọn một segment, trông giống instance_merge.
    flagged = missing | {e["target"] for e in errors if e["type"] != "scene_leak"}
    candidates = cross_check(d, flagged)
    return errors, candidates


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lô Day 10 (nhóm 57)")
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
