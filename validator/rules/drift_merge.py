"""Ứng viên bbox_drift và instance_merge (phần Người 4).

Dùng lại kết quả ghép của Người 3: cache = {stem: (img, match)} từ cross_candidates_n3.
Chỉ thư viện chuẩn. Ứng viên KHÔNG vào errors.json: phải mở ảnh xem rồi ghi review_log.csv.

Tín hiệu (đo trên lô sạch runs/clean và các seed 6475, 777, 4242; xem REPORT.md):
- Box COCO được sinh từ mask, nên với cặp ghép đúng, box bọc trọn segment. Đo "độ tràn" =
  segment bbox vượt ra ngoài box bao nhiêu px ở cạnh tệ nhất. Tự nhiên <= 2 px (làm tròn) trên
  clean, 6475, 777, 4242; các ca lệch tràn >= 12 px. (Tỉ lệ pixel ngoài box thì yếu với vật nhỏ:
  một box lệch 12 px trên vật 52x64 px chỉ để ~20% pixel ra ngoài.)
- instance_merge: một box cùng lớp KHÁC không ghép được với segment nào của riêng nó, mà lại được
  segment này LẤP ĐẦY (pixel segment trong box / diện tích box). Vật của box đó đã bị gộp vào segment.
  Đo trên các ca đã xem ảnh: merge thật lấp đầy box thừa 0,32–0,98; box chỉ chồng lên vì hai vật
  đứng sát (không phải merge) chỉ 0,02–0,18. Tỉ lệ "box thừa chứa bao nhiêu % segment" thì yếu:
  vật bị gộp nhỏ (người cắt ở mép ảnh) chỉ chiếm 7% segment chung.
- Xét merge TRƯỚC drift: segment bị gộp phình ra ngoài box của vật giữ lại, trông giống box lệch.
- bbox_drift: box cùng lớp lệch khỏi segment: dải ngoài box dày, và không giải thích được bằng merge.
"""

from __future__ import annotations

# ---------------------------------------------------------------- ngưỡng

DRIFT_MIN_PX = 5         # segment tràn ra ngoài box >= 5 px (tự nhiên <= 2, lỗi >= 12)
DRIFT_MIN_REL = 0.01     # và >= 1% cạnh ngắn (vật lớn: box lệch + phóng to vẫn chỉ tràn ~8 px trên con vật ~400 px)
MERGE_MIN_FILL = 0.25    # box thừa được segment lấp đầy >= 25% diện tích (merge thật >= 0,32; chồng tự nhiên <= 0,18)
MERGE_MIN_FRAC = 0.03    # và box thừa chứa >= 3% pixel của segment (bỏ chạm mép lặt vặt)
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
            same = []  # (frac, box_idx, fill) các box cùng lớp có chứa pixel của segment
            for bi, (name, b) in boxes.items():
                if name != s["name"]:
                    continue
                k = m["inside"].get((bi, sid), 0)
                if k:
                    area = max(1, (b[2] - b[0]) * (b[3] - b[1]))
                    same.append((k / s["pixels"], bi, k / area))
            same.sort(reverse=True)
            p = pair_of_seg.get(sid)

            # ---- instance_merge: box cùng lớp không có segment riêng mà bị segment này lấp đầy
            orphans = [(f, bi, fl) for f, bi, fl in same
                       if bi in unmatched_boxes and (p is None or bi != p["box_idx"])
                       and fl >= MERGE_MIN_FILL and f >= MERGE_MIN_FRAC]
            owner = [(f, bi, fl) for f, bi, fl in same if p is not None and bi == p["box_idx"]] or \
                    [x for x in same if x not in orphans][:1]
            if orphans and (owner or len(orphans) >= 2):
                parts = (owner + orphans)[:3]
                out.append({
                    "image": stem,
                    "type": "instance_merge",
                    "reason": f"segment {sid} '{s['name']}' ({s['pixels']} px) trải trên {len(parts)} box '{s['name']}': "
                              + ", ".join(f"box #{bi} chứa {int(f * 100)}% segment, được lấp đầy {int(fl * 100)}%" for f, bi, fl in parts)
                              + ". Box thừa không có segment riêng. Mở ảnh: có phải hai vật riêng bị gộp thành một segment?",
                    "seg_id": sid,
                    "seg_bbox_px": list(s["bbox"]),
                    "box_px": [list(boxes[bi][1]) for _, bi, _ in parts],
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
