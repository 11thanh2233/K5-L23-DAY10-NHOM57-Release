"""Luật panoptic của Người 2 (Đinh Đức Hiếu): invalid_category_id, thing_overlap.

Mỗi luật là một hàm thuần: nhận dữ liệu của MỘT ảnh, trả True/False.
check_panoptic_rules trong validate.py gọi các hàm này.

Chỉ thư viện chuẩn + scripts/pngutil.py. Không đọc gì ngoài delivery.
AREA_TOL phải đo lại trên lô sạch: xem REPORT.md.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))  # validator/rules -> repo/scripts
from pngutil import read_rgb  # noqa: E402

# ---------------------------------------------------------------- ngưỡng (đo lại trên lô sạch)

AREA_TOL = 0  # px: area khai được phép lớn hơn số pixel thật bao nhiêu


# ---------------------------------------------------------------- tiện ích dùng chung

def segment_pixel_counts(mask_path: Path) -> Counter:
    """Đếm số pixel của từng segment id trong mask panoptic (id = R + G*256 + B*256^2)."""
    _, _, px = read_rgb(mask_path)
    rgb = Counter(zip(px[0::3], px[1::3], px[2::3]))  # đếm theo bộ màu, nhanh hơn duyệt từng pixel
    return Counter({r + g * 256 + b * 65536: n for (r, g, b), n in rgb.items()})


# ---------------------------------------------------------------- luật panoptic (một ảnh)

def has_invalid_category(segments: list[dict], category_ids: set[int]) -> bool:
    """invalid_category_id: có segment mang category_id không có trong categories."""
    return any(s["category_id"] not in category_ids for s in segments)


def overlapped_segments(segments: list[dict], counts: Counter, tol: int = AREA_TOL) -> list[int]:
    """Các segment có area khai lớn hơn số pixel thật quá tol (bị vật khác đè)."""
    return [s["id"] for s in segments
            if s["id"] != 0 and s["area"] - counts.get(s["id"], 0) > tol]


def has_thing_overlap(segments: list[dict], mask_path: Path, tol: int = AREA_TOL) -> bool:
    """thing_overlap: có segment khai area nhiều hơn số pixel thật trong mask."""
    return bool(overlapped_segments(segments, segment_pixel_counts(mask_path), tol))
