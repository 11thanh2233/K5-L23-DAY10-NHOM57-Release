"""Luật nhãn detection của Người 2 (Đinh Đức Hiếu): invalid_class, bbox_out_of_bounds, duplicate_box.

Mỗi luật là một hàm thuần: nhận dữ liệu của MỘT ảnh, trả True/False.
check_label_rules trong validate.py gọi các hàm này.

Chỉ thư viện chuẩn. Không đọc gì ngoài delivery.
Các ngưỡng (*_TOL) phải đo lại trên lô sạch: xem REPORT.md.
"""

from __future__ import annotations

Box = tuple[int, float, float, float, float]  # (class_id, xc, yc, w, h) chuẩn hoá 0-1

# ---------------------------------------------------------------- ngưỡng (đo lại trên lô sạch)

BOUNDS_TOL = 1e-3   # phần của cạnh ảnh; chỉ chừa sai số làm tròn của nhãn YOLO
SIZE_TOL = 1.0      # px: hai box lặp gần như cùng w, h
CENTER_TOL = 6.0    # px: box lặp lệch tâm 1–2 px ở seed luyện tập; nới 6 px phòng đề ẩn lệch nhiều hơn. Cặp tự nhiên cùng kích thước gần nhất lệch ~12 px (đo trên clean, r6475, r777)


# ---------------------------------------------------------------- tiện ích dùng chung

def yolo_to_xyxy(box: Box, width: int, height: int) -> tuple[float, float, float, float]:
    """Box YOLO chuẩn hoá -> (x1, y1, x2, y2) theo pixel."""
    _, xc, yc, w, h = box
    return ((xc - w / 2) * width, (yc - h / 2) * height,
            (xc + w / 2) * width, (yc + h / 2) * height)


def yolo_to_cxcywh(box: Box, width: int, height: int) -> tuple[float, float, float, float]:
    """Box YOLO chuẩn hoá -> (cx, cy, w, h) theo pixel."""
    _, xc, yc, w, h = box
    return xc * width, yc * height, w * width, h * height


# ---------------------------------------------------------------- luật detection (một ảnh)

def has_invalid_class(boxes: list[Box], class_ids: set[int]) -> bool:
    """invalid_class: có box mang class_id không nằm trong classes.txt."""
    return any(b[0] not in class_ids for b in boxes)


def is_out_of_bounds(box: Box, tol: float = BOUNDS_TOL) -> bool:
    """Một box có mép nào vượt ra ngoài [0, 1] quá tol không."""
    _, xc, yc, w, h = box
    return (xc - w / 2 < -tol or yc - h / 2 < -tol
            or xc + w / 2 > 1 + tol or yc + h / 2 > 1 + tol)


def has_out_of_bounds(boxes: list[Box], tol: float = BOUNDS_TOL) -> bool:
    """bbox_out_of_bounds: có ít nhất một box tràn khỏi ảnh."""
    return any(is_out_of_bounds(b, tol) for b in boxes)


def is_duplicate_pair(a: Box, b: Box, width: int, height: int,
                      size_tol: float = SIZE_TOL, center_tol: float = CENTER_TOL) -> bool:
    """Hai box là bản lặp: cùng lớp, cùng kích thước, tâm lệch rất ít.
    Không dùng IoU: cặp box tự nhiên của COCO có thể chồng nhau tới IoU ~0,66
    nhưng hầu như không bao giờ cùng kích thước tới từng pixel."""
    if a[0] != b[0]:
        return False
    acx, acy, aw, ah = yolo_to_cxcywh(a, width, height)
    bcx, bcy, bw, bh = yolo_to_cxcywh(b, width, height)
    same_size = abs(aw - bw) <= size_tol and abs(ah - bh) <= size_tol
    close = abs(acx - bcx) <= center_tol and abs(acy - bcy) <= center_tol
    return same_size and close


def has_duplicate_box(boxes: list[Box], width: int, height: int) -> bool:
    """duplicate_box: có một cặp box lặp trong ảnh."""
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if is_duplicate_pair(boxes[i], boxes[j], width, height):
                return True
    return False
