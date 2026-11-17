#!/usr/bin/env python3
"""Create detection and panoptic deliveries plus ground truth for one or more seeds.

Does not detect errors. After a team writes errors.json, score with score_findings.py.

  python scripts/download_public.py --dataset coco500
  python scripts/run_lab.py --seeds 11
  python scripts/score_findings.py --run runs/s11 --run runs/p11
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SOURCE = ROOT / "data_source" / "coco500"


def python(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject detection and panoptic faults for the given seeds")
    parser.add_argument("--seeds", default="11,22,33")
    parser.add_argument("--fault-count", type=int, default=8)
    args = parser.parse_args()
    images = list(SOURCE.rglob("images/train2017/*.jpg")) if SOURCE.exists() else []
    if len(images) < 20 or not (ROOT / "data_source" / "coco_panoptic500" / "panoptic.json").is_file():
        raise SystemExit("Chưa có 500 ảnh. Chạy: python scripts/download_public.py --dataset coco500")
    seeds = [str(int(part)) for part in args.seeds.split(",") if part.strip()]
    jobs = []
    for seed in seeds:
        jobs.append((f"s{seed}", seed, str(args.fault_count), "inject_faults.py"))
        jobs.append((f"p{seed}", seed, str(args.fault_count), "inject_panoptic.py"))
    created = []
    for index, (name, seed, count, injector) in enumerate(jobs):
        out = ROOT / "runs" / name
        python(injector, "--seed", seed, "--fault-count", count, "--out", str(out))
        release = json.loads((out / "delivery" / "release.json").read_text(encoding="utf-8"))
        python("lineage.py", "record", "--event", "inject", "--seed", seed, "--release-id", release["release_id"], "--detail", name)
        created.append((name, release["release_id"]))
        if index == 0:
            python("lineage.py", "record", "--event", "train", "--release-id", release["release_id"], "--run-id", "R-021")
    print()
    print("Đã tạo delivery và ground truth. Chưa có danh sách lỗi của nhóm.")
    print("Ghi errors.json trong từng thư mục run, rồi chấm từng seed một:")
    for name, _ in created:
        if name.startswith("s"):
            seed = name[1:]
            print(f"python scripts/score_findings.py --run runs/s{seed} --run runs/p{seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
