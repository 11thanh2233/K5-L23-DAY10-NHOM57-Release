"""Ứng viên bbox_drift và instance_merge (phần Người 4).

Dùng lại kết quả ghép của Người 3: cache = {stem: (img, match)} từ cross_candidates_n3.
Chỉ thư viện chuẩn. Ứng viên KHÔNG vào errors.json: phải mở ảnh xem rồi ghi review_log.csv.

Tín hiệu (đo trên lô sạch runs/clean và các seed 6475, 777, 4242; xem REPORT.md):
- Box COCO được sinh từ mask, nên với cặp ghép đúng, box bọc trọn segment. Đo "độ tràn" =
  segment bbox vượt ra ngoài box bao nhiêu px ở cạnh tệ nhất. Tự nhiên <= 2 px (làm tròn) trên
  clean, 6475, 777, 4242; các ca lệch tràn >= 12 px. (Tỉ lệ pixel ngoài box thì yếu với vật nhỏ:
  một box lệch 12 px trên vật 52x64 px chỉ để ~20% pixel ra ngoài.)
- instance_merge: một segment có pixel nằm đáng kể trong một box cùng lớp KHÁC mà box đó
  không ghép được với segment nào của riêng nó (vật của box đó đã bị gộp vào segment này).
- bbox_drift: box cùng lớp lệch khỏi segment: dải ngoài box dày, và không giải thích được bằng merge.
"""

from __future__ import annotations

# ---------------------------------------------------------------- ngưỡng

DRIFT_MIN_PX = 5         # segment tràn ra ngoài box >= 5 px (tự nhiên <= 2, lỗi >= 12)
DRIFT_MIN_REL = 0.05     # và >= 5% cạnh ngắn của segment (bỏ lệch 1 px trên vật tí hon)
MERGE_MIN_FRAC = 0.20    # box cùng lớp thứ hai chứa >= 20% pixel của segment
MIN_SEG_PX = 100         # bỏ segment quá nhỏ: không xem được bằng mắt, dễ nhiễu


def overflow_px(box: tuple[int, int, int, int], seg_bbox: tuple[int, int, int, int]) -> int:
    """Segment bbox vượt ra ngoài box bao nhiêu px, ở cạnh tệ nhất (0 nếu box bọc trọn)."""
    return max(0, box[0] - seg_bbox[0], box[1] - seg_bbox[1], seg_bbox[2] - box[2], seg_bbox[3] - box[3])


def drift_merge_candidates(cache: dict) -> list[dict]:
    """cache: {stem: (img, match)} của Người 3. Trả về list ứng viên {"image", "type", "reason", ...}."""
    out = []
    for stem, (img, m) in sorted(cache.items()):
        boxes = {bi: (name, b) for bi, name, b in img["boxes"]}
        unmatched_boxes = set(m["unmatched_boxes"])
        pair_of_seg = {p["seg_id"]: p for p in m["pairs"]}
        flagged = False  # mỗi ảnh nhiều nhất một lỗi: một ứng viên drift/merge mỗi ảnh là đủ

        for sid, s in sorted(img["segs"].items(), key=lambda kv: -kv[1]["pixels"]):
            if flagged or s["pixels"] < MIN_SEG_PX:
                continue
            same = []  # (frac, box_idx) các box cùng lớp có chứa pixel của segment
            for bi, (name, b) in boxes.items():
                if name != s["name"]:
                    continue
                k = m["inside"].get((bi, sid), 0)
                if k:
                    same.append((k / s["pixels"], bi))
            same.sort(reverse=True)
            p = pair_of_seg.get(sid)

            # ---- instance_merge: segment trải sang box cùng lớp không có segment riêng
            orphans = [(f, bi) for f, bi in same
                       if f >= MERGE_MIN_FRAC and bi in unmatched_boxes and (p is None or bi != p["box_idx"])]
            owner = [(f, bi) for f, bi in same if p is not None and bi == p["box_idx"]] or \
                    [(f, bi) for f, bi in same if f >= MERGE_MIN_FRAC and (f, bi) not in orphans][:1]
            if orphans and (owner or len(orphans) >= 2):
                parts = (owner + orphans)[:3]
                out.append({
                    "image": stem,
                    "type": "instance_merge",
                    "reason": f"segment {sid} '{s['name']}' ({s['pixels']} px) trải trên {len(parts)} box '{s['name']}': "
                              + ", ".join(f"box #{bi} chứa {int(f * 100)}%" for f, bi in parts)
                              + ". Box thừa không có segment riêng. Mở ảnh: có phải hai vật riêng bị gộp thành một segment?",
                    "seg_id": sid,
                    "seg_bbox_px": list(s["bbox"]),
                    "box_px": [list(boxes[bi][1]) for _, bi in parts],
                    "pan_class": s["name"],
                })
                flagged = True
                continue

            # ---- bbox_drift: segment tràn ra ngoài box cùng lớp của nó
            if p is not None:
                b = boxes[p["box_idx"]][1]
                inside = m["inside"].get((p["box_idx"], sid), 0)
            elif same and same[0][1] in unmatched_boxes and same[0][0] >= 0.3:
                # box lệch nhiều tới mức không ghép được, nhưng vẫn chồng lên segment
                b = boxes[same[0][1]][1]
                inside = int(same[0][0] * s["pixels"])
            else:
                continue
            ov = overflow_px(b, s["bbox"])
            short = max(1, min(s["bbox"][2] - s["bbox"][0], s["bbox"][3] - s["bbox"][1]))
            if ov >= DRIFT_MIN_PX and ov / short >= DRIFT_MIN_REL:
                out.append({
                    "image": stem,
                    "type": "bbox_drift",
                    "reason": f"segment {sid} '{s['name']}' bbox {list(s['bbox'])} tràn {ov} px ra ngoài box {list(b)} "
                              f"({int(100 * ov / short)}% cạnh ngắn; tự nhiên <= 2 px); box chứa {int(100 * inside / s['pixels'])}% "
                              f"pixel của segment. Mở ảnh: box có lệch khỏi vật không?",
                    "seg_id": sid,
                    "seg_bbox_px": list(s["bbox"]),
                    "box_px": list(b),
                    "pan_class": s["name"],
                })
                flagged = True
    return out
