#!/usr/bin/env python3
"""Truy vết ticket (Pha 5). Chỉ thư viện chuẩn.

  python validator/trace_query.py <delivery> --out trace.json [--class truck] [--scenes scene_166 scene_507] [--old v1.2]

Mặc định tự đọc từ lô:
  - lớp: tên lớp đầu tiên trong `...` của incoming/ticket.md có trong classes.txt
  - cảnh: mọi scene_<số> trong ticket
  - guideline cũ: mọi phiên bản trong jobs.csv thấp hơn phiên bản đầu tiên (trong changelog) nhắc tới lớp đó
Guideline lấy theo JOB (jobs.csv), không theo ảnh (metadata có thể chính là lỗi guideline_mismatch).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--scenes", nargs="*")
    ap.add_argument("--old", nargs="*", help="các phiên bản guideline cũ")
    a = ap.parse_args()
    d = a.delivery

    # classes.txt: mỗi dòng "id tên"
    classes = dict(reversed(l.split(maxsplit=1)) for l in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if l.strip())
    ticket = (d / "incoming" / "ticket.md").read_text(encoding="utf-8")
    cls = a.cls or next(w for w in re.findall(r"`([^`]+)`", ticket) if w in classes)
    cls_id = classes[cls]
    scenes = set(a.scenes or re.findall(r"scene_\d+", ticket))

    jobs = {r["job_id"]: r for r in csv.DictReader(open(d / "jobs.csv", encoding="utf-8"))}
    if a.old:
        old = set(a.old)
    else:
        # changelog: mục "## vX" đầu tiên (từ cũ tới mới) có nhắc tới lớp -> phiên bản đổi quy tắc
        sections = re.split(r"^##\s+", (d / "guideline" / "changelog.md").read_text(encoding="utf-8"), flags=re.M)
        changed = min(ver(s.split()[0]) for s in sections[1:] if f"`{cls}`" in s)
        old = {j["guideline"] for j in jobs.values() if ver(j["guideline"]) < changed}

    def has_cls(image: str) -> bool:
        f = d / "labels" / f"{image}.txt"
        return f.is_file() and any(
            line.split() and line.split()[0] == str(cls_id) for line in f.read_text().splitlines()
        )

    tier_a, tier_b, notify = [], [], set()
    for it in json.load(open(d / "metadata.json", encoding="utf-8"))["items"]:
        job = jobs.get(it["job_id"])
        if not job or job["guideline"] not in old or not has_cls(it["image"]):
            continue
        (tier_a if it["scene_id"] in scenes else tier_b).append(it["image"])
        notify.update([job["annotator"], job["reviewer"]])

    out = {"tier_a": sorted(tier_a), "tier_b": sorted(tier_b), "notify": sorted(notify)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"lớp={cls} (id {cls_id}) cảnh={sorted(scenes)} guideline cũ={sorted(old)}")
    print(f"tier_a={len(tier_a)} tier_b={len(tier_b)} notify={sorted(notify)}")


if __name__ == "__main__":
    main()
