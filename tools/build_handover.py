#!/usr/bin/env python3
"""Dựng lô bàn giao v2 (sản phẩm DETECTION) từ lô v1 + errors.json đã chốt. Pha 4, phần Người 5.

    py -X utf8 tools/build_handover.py --run runs/r6475 [--checked-hash 000000005477,000000020553]

Không sửa gì trong delivery/ (v1). Ghi runs/r<seed>/handover/<release_id>_v2/:
  images/, labels/        ảnh + nhãn GIỮ NGUYÊN của v1, trừ ảnh phải gán lại
  rework_queue.csv        image,type,annotator,reviewer,action (người theo jobs.csv)
  manifest.csv            file,sha256 cho mọi file trong images/ và labels/ (hash tính lại từ bytes)
  label_summary.csv       class,count theo classes.txt, dòng cuối TOTAL
  truyvet.csv             image,scene_id,split,job_id,annotator,reviewer,guideline (guideline theo JOB)
  README.txt              theo templates/README.txt

Phân loại lỗi (GUIDE Pha 4):
  - sửa ngay trong v2: wrong_hash (đã mở ảnh kiểm: còn nguyên -> ghi hash mới), guideline_mismatch
    (lấy guideline theo job), scene_leak (đưa cả cảnh về split đa số của cảnh)
  - lỗi nhãn detection / thiếu file -> rework_queue, rời v2
  - lỗi chỉ ở panoptic -> ảnh ở lại v2, ghi vào README để báo team panoptic
Sau khi chạy: pack_release.py, lineage release --parent, check_handover.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

FIX_IN_V2 = {"wrong_hash", "guideline_mismatch", "scene_leak"}
DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box", "class_swap", "bbox_drift", "missing_box"}
PAN_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
ACTION = {
    "missing_image": "giao lại file ảnh gốc, kiểm lại nhãn",
    "invalid_class": "gán lại lớp cho box có class_id ngoài 0–79",
    "bbox_out_of_bounds": "vẽ lại box tràn khỏi ảnh",
    "duplicate_box": "xoá box lặp",
    "class_swap": "gán lại lớp đúng cho box",
    "bbox_drift": "vẽ lại box khớp vật",
    "missing_box": "gán thêm box cho vật bị thiếu",
    "wrong_hash": "giao lại ảnh gốc (ảnh hỏng)",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p: Path, header: list[str], rows: list[list]) -> None:
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng lô bàn giao v2")
    ap.add_argument("--run", required=True, help="runs/r<seed> (có delivery/ và errors.json)")
    ap.add_argument("--checked-hash", default="",
                    help="ảnh wrong_hash ĐÃ MỞ KIỂM là còn nguyên (phẩy ngăn cách); ảnh wrong_hash khác coi như hỏng -> rework")
    args = ap.parse_args()
    run = Path(args.run)
    d = run / "delivery"
    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    jobs = {r["job_id"]: r for r in read_csv(d / "jobs.csv")}
    names = [ln.split(" ", 1)[1].strip() for ln in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    errors = json.loads((run / "errors.json").read_text(encoding="utf-8"))["errors"]
    intact = {s.strip() for s in args.checked_hash.split(",") if s.strip()}

    by_image = {e["target"]: e["type"] for e in errors if e["type"] != "scene_leak"}
    leak_scenes = {e["target"] for e in errors if e["type"] == "scene_leak"}
    unknown = set(by_image.values()) - FIX_IN_V2 - DET_REWORK - PAN_ONLY
    if unknown:
        raise SystemExit(f"loại lỗi lạ trong errors.json: {unknown}")

    # ảnh rời v2 để gán lại
    rework = {s: t for s, t in by_image.items() if t in DET_REWORK or (t == "wrong_hash" and s not in intact)}
    hash_fixed = sorted(s for s, t in by_image.items() if t == "wrong_hash" and s in intact)
    guide_fixed = sorted(s for s, t in by_image.items() if t == "guideline_mismatch")
    pan_only = sorted((s, t) for s, t in by_image.items() if t in PAN_ONLY)

    # scene_leak: cả cảnh về split đa số (hoà thì train)
    split_of = {}
    for sc in leak_scenes:
        c = Counter(meta[s]["split"] for s in man if meta[s]["scene_id"] == sc)
        split_of[sc] = "train" if c["train"] >= c["val"] else "val"

    v2 = run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()
    keep = [s for s in sorted(man) if s not in rework]
    for s in keep:
        shutil.copyfile(d / man[s]["image"], v2 / "images" / Path(man[s]["image"]).name)
        shutil.copyfile(d / man[s]["label"], v2 / "labels" / Path(man[s]["label"]).name)  # nhãn không sửa tay

    def owner(s):
        j = jobs[meta[s]["job_id"]]
        return j["annotator"], j["reviewer"]

    write_csv(v2 / "rework_queue.csv", ["image", "type", "annotator", "reviewer", "action"],
              [[s, t, *owner(s), ACTION[t]] for s, t in sorted(rework.items())])
    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir() if p.is_file())
    write_csv(v2 / "manifest.csv", ["file", "sha256"], [[p.relative_to(v2).as_posix(), sha(p)] for p in files])

    counts = Counter()
    for s in keep:
        for ln in (v2 / "labels" / Path(man[s]["label"]).name).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                counts[names[int(float(ln.split()[0]))]] += 1
    write_csv(v2 / "label_summary.csv", ["class", "count"],
              [[n, counts[n]] for n in names if counts[n]] + [["TOTAL", sum(counts.values())]])

    tv = []
    for s in keep:
        m = meta[s]
        a, r = owner(s)
        tv.append([s, m["scene_id"], split_of.get(m["scene_id"], m["split"]), m["job_id"], a, r, jobs[m["job_id"]]["guideline"]])
    write_csv(v2 / "truyvet.csv", ["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"], tv)

    # README.txt
    n_err = len({e["target"] for e in errors})
    rate = n_err / len(man)
    g = {}
    for j, row in sorted(jobs.items()):
        g.setdefault(row["guideline"], []).append(j)
    guide = ", ".join(f"{v} ({js[0]}-{js[-1]})" if len(js) > 1 else f"{v} ({js[0]})" for v, js in sorted(g.items()))
    rw_people = sorted({f"{s} -> {'/'.join(owner(s))}" for s in rework})
    leak_txt = "; ".join(f"{sc} đưa cả cảnh về {sp}" for sc, sp in sorted(split_of.items())) or "không có"
    lines = [
        f"Release: {rid}_v2",
        f"Parent: {rid}",
        f"Số ảnh: {len(keep)}",
        f"Số nhãn: {sum(counts.values())}",
        f"Guideline: {guide}",
        f"QC v1: {n_err}/{len(man)} = {rate * 100:.1f}%".replace(".", ",", 1),
        f"Kết luận v1: {'Hold' if rate > 0.02 else 'Release'} — {n_err} ảnh/cảnh lỗi trên {len(man)} ảnh "
        f"({rate * 100:.1f}%) {'vượt' if rate > 0.02 else 'không vượt'} ngưỡng 2% (Day 7)".replace(".", ",", 1),
        f"Kết luận v2: Release — tách {len(rework)} ảnh lỗi nhãn detection/thiếu file sang rework_queue; "
        f"sửa trong v2 {len(hash_fixed)} hash, {len(guide_fixed)} guideline, {len(split_of)} cảnh rò split; "
        f"không còn lỗi detection đã biết trong {len(keep)} ảnh",
        "Ghi chú: "
        f"(1) Hash: {', '.join(hash_fixed) or 'không có'} — đã mở ảnh, ảnh còn nguyên và đúng nội dung; manifest v1 ghi nhầm hash của ảnh khác, "
        "manifest.csv v2 ghi sha256 tính lại từ bytes. "
        f"(2) Guideline: {', '.join(guide_fixed) or 'không có'} — truyvet.csv lấy guideline theo job trong jobs.csv, không theo metadata ảnh. "
        f"(3) Split: {leak_txt} (split đa số của cảnh) để không rò train/val. "
        f"(4) Rework giao lại đúng người gán/người kiểm theo jobs.csv: {', '.join(rw_people) or 'không có'}. "
        f"(5) Lỗi chỉ ở panoptic, ảnh ở lại v2 vì nhãn detection vẫn đúng, báo team panoptic: "
        f"{', '.join(f'{s} ({t})' for s, t in pan_only) or 'không có'}. "
        "(6) Nhãn detection trong v2 không sửa tay; v1 giữ nguyên.",
    ]
    (v2 / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{v2}: {len(keep)} ảnh, {sum(counts.values())} nhãn, rework {len(rework)}, panoptic-only {len(pan_only)}, "
          f"sửa hash {len(hash_fixed)}, guideline {len(guide_fixed)}, cảnh rò {len(split_of)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
