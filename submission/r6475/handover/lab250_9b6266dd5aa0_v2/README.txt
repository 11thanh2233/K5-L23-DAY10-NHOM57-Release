Release: lab250_9b6266dd5aa0_v2
Parent: lab250_9b6266dd5aa0
Số ảnh: 240
Số nhãn: 1598
Guideline: v1.2 (J01-J03), v1.3 (J04-J10)
QC v1: 21/250 = 8,4%
Kết luận v1: Hold — 21 ảnh/cảnh lỗi trên 250 ảnh (8,4%) vượt ngưỡng 2% (Day 7)
Kết luận v2: Release — tách 10 ảnh lỗi nhãn detection/thiếu file sang rework_queue; sửa trong v2 2 hash, 1 guideline, 1 cảnh rò split; không còn lỗi detection đã biết trong 240 ảnh
Ghi chú: (1) Hash: 000000005477, 000000020553 — đã mở ảnh, ảnh còn nguyên và đúng nội dung; manifest v1 ghi nhầm hash của ảnh khác, manifest.csv v2 ghi sha256 tính lại từ bytes. (2) Guideline: 000000015660 — truyvet.csv lấy guideline theo job trong jobs.csv, không theo metadata ảnh. (3) Split: scene_861 đưa cả cảnh về train (split đa số của cảnh) để không rò train/val. (4) Rework giao lại đúng người gán/người kiểm theo jobs.csv: 000000000785 -> A02/Q01, 000000005001 -> A05/Q03, 000000007784 -> A02/Q03, 000000009483 -> A02/Q03, 000000012062 -> A03/Q03, 000000014038 -> A04/Q03, 000000017959 -> A04/Q02, 000000018380 -> A04/Q02, 000000018737 -> A04/Q02, 000000022589 -> A03/Q03. (5) Lỗi chỉ ở panoptic, ảnh ở lại v2 vì nhãn detection vẫn đúng, báo team panoptic: 000000003553 (thing_overlap), 000000007795 (instance_merge), 000000017436 (category_swap), 000000021167 (invalid_category_id), 000000021879 (thing_overlap), 000000021903 (instance_merge), 000000023034 (invalid_category_id). (6) Nhãn detection trong v2 không sửa tay; v1 giữ nguyên.
