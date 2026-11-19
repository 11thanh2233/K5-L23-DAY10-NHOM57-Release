#!/usr/bin/env python3
"""Công cụ xem ảnh ứng viên (phần Người 4). Dùng Pillow (được phép cho công cụ xem ảnh, KHÔNG cho validator).

    py -X utf8 tools/review_viewer.py <delivery> <candidates.json> --out <thư_mục_ảnh>

Mỗi ứng viên ra một PNG: trái là toàn ảnh, phải là vùng quanh vật phóng to.
  - đỏ:   box detection của ứng viên (kèm tên lớp detection)
  - xanh: viền segment panoptic của ứng viên (kèm tên lớp panoptic), tô mờ bên trong
  - vàng mảnh: các box detection khác trong ảnh, để thấy bối cảnh
Kèm index.html (xem cả hàng đợi trong trình duyệt) và review_draft.csv (image,type,verdict,note để điền).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "validator"))
import pngutil  # noqa: E402
from validate import Delivery  # noqa: E402

RED, GREEN, YELLOW = (230, 40, 40), (20, 210, 90), (250, 210, 40)
PANEL = 640  # px chiều rộng mỗi nửa
try:
    FONT = ImageFont.load_default(size=16)
except TypeError:  # Pillow < 10.1
    FONT = ImageFont.load_default()


def seg_mask(mask_path: Path, seg_id: int) -> Image.Image:
    """Ảnh 'L' 255 ở pixel thuộc seg_id (id = R + G*256 + B*256^2)."""
    W, H, rgb = pngutil.read_rgb(mask_path)
    r, g, b = seg_id & 255, (seg_id >> 8) & 255, (seg_id >> 16) & 255
    out = bytearray(W * H)
    for i in range(W * H):
        j = 3 * i
        if rgb[j] == r and rgb[j + 1] == g and rgb[j + 2] == b:
            out[i] = 255
    return Image.frombytes("L", (W, H), bytes(out))


def as_boxes(v) -> list[list[int]]:
    if not v:
        return []
    return [list(x) for x in v] if isinstance(v[0], (list, tuple)) else [list(v)]


def render(d: Delivery, cand: dict, out_path: Path) -> None:
    stem = cand["image"]
    img = Image.open(d.path(stem, "image")).convert("RGB")
    W, H = img.size
    draw_img = img.copy()
    dr = ImageDraw.Draw(draw_img)

    # bối cảnh: mọi box detection, vàng mảnh
    for cid, xc, yc, w, h in d.read_boxes(stem):
        x1, y1, x2, y2 = (xc - w / 2) * W, (yc - h / 2) * H, (xc + w / 2) * W, (yc + h / 2) * H
        dr.rectangle([x1, y1, x2, y2], outline=YELLOW, width=1)

    region = []
    sid = cand.get("seg_id")
    if sid is not None and d.path(stem, "mask").is_file():
        m = seg_mask(d.path(stem, "mask"), int(sid))
        if m.size == img.size:
            fill = Image.new("RGB", img.size, GREEN)
            draw_img = Image.composite(Image.blend(draw_img, fill, 0.35), draw_img, m)
            edge = m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
            draw_img.paste(GREEN, mask=edge)
            dr = ImageDraw.Draw(draw_img)
            bb = m.getbbox()
            if bb:
                region.append(list(bb))
                if cand.get("pan_class"):
                    dr.text((bb[0] + 2, max(0, bb[1] - 18)), "pan: " + cand["pan_class"], fill=GREEN, font=FONT)
    for b in as_boxes(cand.get("box_px")):
        dr.rectangle(b, outline=RED, width=3)
        region.append(b)
        if cand.get("det_class"):
            dr.text((b[0] + 3, b[3] + 2), "det: " + cand["det_class"], fill=RED, font=FONT)
    region += as_boxes(cand.get("seg_bbox_px"))

    # vùng phóng to quanh vật, chừa lề 40% kích thước vùng
    if region:
        x1 = min(r[0] for r in region); y1 = min(r[1] for r in region)
        x2 = max(r[2] for r in region); y2 = max(r[3] for r in region)
        mx, my = max(16, int(0.4 * (x2 - x1))), max(16, int(0.4 * (y2 - y1)))
        crop = draw_img.crop((max(0, x1 - mx), max(0, y1 - my), min(W, x2 + mx), min(H, y2 + my)))
    else:
        crop = draw_img
    left = draw_img.resize((PANEL, max(1, round(H * PANEL / W))))
    scale = min(PANEL / crop.width, 3 * PANEL / max(1, crop.height), 6.0)
    right = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.LANCZOS)
    sheet = Image.new("RGB", (PANEL * 2 + 10, max(left.height, right.height)), (30, 30, 30))
    sheet.paste(left, (0, 0))
    sheet.paste(right, (PANEL + 10, 0))
    sheet.save(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vẽ ứng viên lên ảnh để review")
    ap.add_argument("delivery")
    ap.add_argument("candidates")
    ap.add_argument("--out", required=True, help="thư mục ghi PNG + index.html + review_draft.csv")
    args = ap.parse_args()
    d = Delivery(Path(args.delivery))
    cands = json.loads(Path(args.candidates).read_text(encoding="utf-8"))["candidates"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, cards = [], []
    for i, c in enumerate(cands, 1):
        name = f"{i:03d}_{c['image']}_{c['type'].replace('|', '-')}.png"
        render(d, c, out / name)
        rows.append({"image": c["image"], "type": c["type"], "verdict": "", "note": ""})
        cards.append(f"<section><h2>{i}. {html.escape(c['image'])} · {html.escape(c['type'])}</h2>"
                     f"<p>{html.escape(c.get('reason', ''))}</p><img src='{name}' alt='{html.escape(c['image'])}'></section>")
        print(f"[{i}/{len(cands)}] {name}")
    with (out / "review_draft.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "type", "verdict", "note"])
        w.writeheader()
        w.writerows(rows)
    (out / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Hàng đợi review</title>"
        "<style>body{font-family:system-ui;background:#111;color:#eee;margin:16px}img{max-width:100%}"
        "section{margin-bottom:28px}p{color:#bbb;max-width:90ch}</style>"
        "<p>Đỏ: box detection của ứng viên · Xanh: segment panoptic · Vàng: các box khác. "
        "Ghi review_log.csv: verdict confirmed/rejected, note nói rõ thấy gì (≥ 20 ký tự). "
        "Ứng viên 'class_swap|category_swap': chọn đúng MỘT loại theo ảnh.</p>" + "".join(cards),
        encoding="utf-8")
    print(f"-> {out / 'index.html'}, {out / 'review_draft.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
