#!/usr/bin/env python3
"""Inject panoptic label errors with random.Random(seed).

- invalid_category_id: a thing segment is given a class id outside the category list.
- thing_overlap: part of one thing is painted with another thing's id, while the
  donor's area and bbox still claim the lost pixels. A panoptic mask cannot store
  two ids on one pixel, so the overlap shows up as area > pixel count.
- category_swap: pixels stay, the class id changes to another thing class.
- instance_merge: two thing instances of the same class become one region.

Ground truth is <out>/_private/truth.json. Scoring uses (type, target) only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pngutil  # noqa: E402

TYPES = ["invalid_category_id", "thing_overlap", "category_swap", "instance_merge"]
KIND_ORDER = {"instance_merge": 0, "thing_overlap": 1, "category_swap": 2, "invalid_category_id": 3}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def measure(pixels: bytes, width: int) -> dict[int, dict]:
    found: dict[int, dict] = {}
    for index in range(0, len(pixels), 3):
        segment = pngutil.segment_id(pixels, index)
        if segment == 0:
            continue
        x = (index // 3) % width
        y = (index // 3) // width
        slot = found.get(segment)
        if slot is None:
            found[segment] = {"area": 1, "x0": x, "y0": y, "x1": x, "y1": y}
        else:
            slot["area"] += 1
            slot["x0"] = min(slot["x0"], x)
            slot["y0"] = min(slot["y0"], y)
            slot["x1"] = max(slot["x1"], x)
            slot["y1"] = max(slot["y1"], y)
    return found


def paint(pixels: bytearray, source: int, dest: int) -> int:
    red, green, blue = pngutil.segment_rgb(dest)
    moved = 0
    for index in range(0, len(pixels), 3):
        if pngutil.segment_id(pixels, index) != source:
            continue
        pixels[index] = red
        pixels[index + 1] = green
        pixels[index + 2] = blue
        moved += 1
    return moved


def thing_ids(document: dict) -> set[int]:
    return {category["id"] for category in document["categories"] if category.get("isthing")}


def segments_of(annotation: dict, things: set[int]) -> list[dict]:
    return [segment for segment in annotation["segments_info"] if not segment.get("iscrowd") and segment["category_id"] in things]


def can_merge(annotation: dict, things: set[int]) -> bool:
    counts: dict[int, int] = {}
    for segment in segments_of(annotation, things):
        counts[segment["category_id"]] = counts.get(segment["category_id"], 0) + 1
    return any(count >= 2 for count in counts.values())


def apply_invalid(annotation: dict, things: set[int], rng: random.Random) -> dict | None:
    choices = segments_of(annotation, things)
    if not choices:
        return None
    segment = rng.choice(choices)
    original = segment["category_id"]
    segment["category_id"] = 9999
    return {
        "type": "invalid_category_id",
        "target": Path(annotation["file_name"]).stem,
        "unit": "image",
        "segment_id": segment["id"],
        "from_category": original,
        "to_category": 9999,
    }


def apply_overlap(annotation: dict, pixels: bytearray, width: int, things: set[int], rng: random.Random) -> dict | None:
    stats = measure(pixels, width)
    viable = [segment for segment in segments_of(annotation, things) if stats.get(segment["id"], {}).get("area", 0) >= 4]
    if len(viable) < 2:
        return None
    donor, receiver = rng.sample(viable, 2)
    before = stats[donor["id"]]["area"]
    offsets = [index for index in range(0, len(pixels), 3) if pngutil.segment_id(pixels, index) == donor["id"]]
    steal = max(1, len(offsets) // 3)
    if len(offsets) - steal < 1:
        return None
    red, green, blue = pngutil.segment_rgb(receiver["id"])
    for index in offsets[:steal]:
        pixels[index] = red
        pixels[index + 1] = green
        pixels[index + 2] = blue
    updated = measure(pixels, width).get(receiver["id"])
    if updated is None or measure(pixels, width).get(donor["id"], {}).get("area", 0) >= before:
        return None
    donor["area"] = before
    receiver["area"] = updated["area"]
    receiver["bbox"] = [updated["x0"], updated["y0"], updated["x1"] - updated["x0"] + 1, updated["y1"] - updated["y0"] + 1]
    return {
        "type": "thing_overlap",
        "target": Path(annotation["file_name"]).stem,
        "unit": "image",
        "donor_segment_id": donor["id"],
        "receiver_segment_id": receiver["id"],
    }


def apply_swap(annotation: dict, things: set[int], rng: random.Random) -> dict | None:
    choices = segments_of(annotation, things)
    if not choices:
        return None
    segment = rng.choice(choices)
    others = sorted(things - {segment["category_id"]})
    if not others:
        return None
    original = segment["category_id"]
    segment["category_id"] = rng.choice(others)
    return {
        "type": "category_swap",
        "target": Path(annotation["file_name"]).stem,
        "unit": "image",
        "segment_id": segment["id"],
        "from_category": original,
        "to_category": segment["category_id"],
    }


def apply_merge(annotation: dict, pixels: bytearray, width: int, things: set[int], rng: random.Random) -> dict | None:
    groups: dict[int, list[dict]] = {}
    for segment in segments_of(annotation, things):
        groups.setdefault(segment["category_id"], []).append(segment)
    groups = {category: items for category, items in groups.items() if len(items) >= 2}
    if not groups:
        return None
    category = rng.choice(sorted(groups))
    pair = groups[category]
    pair.sort(key=lambda item: item.get("area") or 0)
    removed = pair[0]
    kept = pair[-1]
    if removed["id"] == kept["id"]:
        return None
    moved = paint(pixels, removed["id"], kept["id"])
    if moved == 0:
        return None
    stats = measure(pixels, width).get(kept["id"])
    if stats is None:
        return None
    kept["area"] = stats["area"]
    kept["bbox"] = [stats["x0"], stats["y0"], stats["x1"] - stats["x0"] + 1, stats["y1"] - stats["y0"] + 1]
    annotation["segments_info"] = [segment for segment in annotation["segments_info"] if segment["id"] != removed["id"]]
    return {
        "type": "instance_merge",
        "target": Path(annotation["file_name"]).stem,
        "unit": "image",
        "category_id": category,
        "kept_segment_id": kept["id"],
        "removed_segment_id": removed["id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject panoptic label errors and write ground truth")
    parser.add_argument("--source", default="data_source/coco_panoptic500")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fault-count", type=int, default=8)
    parser.add_argument("--dev-truth", action="store_true")
    args = parser.parse_args()
    source = Path(args.source)
    document = json.loads((source / "panoptic.json").read_text(encoding="utf-8"))
    things = thing_ids(document)
    by_id = {image["id"]: image for image in document["images"]}
    annotations = {ann["image_id"]: json.loads(json.dumps(ann)) for ann in document["annotations"]}
    if len(annotations) < 2:
        raise SystemExit("Panoptic source is missing. Run scripts/download_public.py --dataset coco500")

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    delivery = out / "delivery"
    (delivery / "images").mkdir(parents=True)
    (delivery / "masks").mkdir(parents=True)
    for image in document["images"]:
        shutil.copyfile(source / "images" / image["file_name"], delivery / "images" / image["file_name"])
        mask_name = Path(annotations[image["id"]]["file_name"]).name
        shutil.copyfile(source / "masks" / mask_name, delivery / "masks" / mask_name)

    rng = random.Random(args.seed)
    kinds = (TYPES * ((args.fault_count + len(TYPES) - 1) // len(TYPES)))[: args.fault_count]
    rng.shuffle(kinds)
    kinds.sort(key=lambda kind: KIND_ORDER[kind])
    used: set[int] = set()
    truths = []
    for kind in kinds:
        image_ids = [image_id for image_id in sorted(annotations) if image_id not in used]
        if kind == "instance_merge":
            image_ids = [image_id for image_id in image_ids if can_merge(annotations[image_id], things)]
        elif kind == "thing_overlap":
            image_ids = [image_id for image_id in image_ids if len(segments_of(annotations[image_id], things)) >= 2]
        else:
            image_ids = [image_id for image_id in image_ids if segments_of(annotations[image_id], things)]
        rng.shuffle(image_ids)
        applied = None
        chosen = None
        for image_id in image_ids:
            annotation = annotations[image_id]
            mask_path = delivery / "masks" / Path(annotation["file_name"]).name
            if kind == "category_swap":
                applied = apply_swap(annotation, things, rng)
            elif kind == "invalid_category_id":
                applied = apply_invalid(annotation, things, rng)
            else:
                width, height, pixels = pngutil.read_rgb(mask_path)
                if kind == "instance_merge":
                    applied = apply_merge(annotation, pixels, width, things, rng)
                else:
                    applied = apply_overlap(annotation, pixels, width, things, rng)
                if applied is not None:
                    pngutil.write_rgb(mask_path, width, height, pixels)
            if applied is not None:
                chosen = image_id
                break
        if applied is None or chosen is None:
            raise SystemExit(f"Not enough images for {kind}. Have {len(annotations)} annotations.")
        used.add(chosen)
        truths.append(applied)

    released = {
        "info": document.get("info", {}),
        "licenses": document.get("licenses", []),
        "categories": document["categories"],
        "images": document["images"],
        "annotations": [annotations[image["id"]] for image in document["images"]],
    }
    (delivery / "panoptic.json").write_text(json.dumps(released, indent=2) + "\n", encoding="utf-8")
    manifest = {}
    for image in document["images"]:
        stem = Path(image["file_name"]).stem
        mask_name = Path(annotations[image["id"]]["file_name"]).name
        manifest[stem] = {
            "image": f"images/{image['file_name']}",
            "mask": f"masks/{mask_name}",
            "image_sha256": sha(delivery / "images" / image["file_name"]),
            "mask_sha256": sha(delivery / "masks" / mask_name),
        }
    (delivery / "manifest.json").write_text(json.dumps({"dataset": "COCO_PANOPTIC500", "items": manifest}, indent=2) + "\n", encoding="utf-8")
    release_id = "panoptic500_" + hashlib.sha256((delivery / "panoptic.json").read_bytes()).hexdigest()[:12]
    (delivery / "release.json").write_text(
        json.dumps({"release_id": release_id, "task": "panoptic", "source": "COCO val2017 panoptic"}, indent=2) + "\n",
        encoding="utf-8",
    )
    private = out / "_private"
    private.mkdir()
    (private / "truth.json").write_text(json.dumps({"seed": args.seed, "task": "panoptic", "errors": truths}, indent=2) + "\n", encoding="utf-8")
    if args.dev_truth:
        print("Ground truth:", truths)
    else:
        print("Ground truth written to", private, "(the validator must not read this folder)")
    print(f"Seed={args.seed}, images={len(annotations)}, faults={len(truths)}, delivery={delivery}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
