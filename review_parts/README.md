# Review ảnh — seed 6475

Mỗi người mở ảnh của mình trong `r6475_img/`, điền **file của mình** `r6475_N<số>.csv`, rồi commit + push bằng tài khoản của mình.
N1 gộp các file thành `runs/r6475/review_log.csv` khi đủ 6 file.

**Cách đọc ảnh:** trái là toàn ảnh, phải là vùng phóng to. Đỏ = box detection của ứng viên · Xanh = segment panoptic · Vàng = các box khác.

**Cách điền:**
- `verdict`: `confirmed` (đúng là lỗi) hoặc `rejected` (lệch tự nhiên: vật bị che, crowd, hai vật đứng sát…).
- `note`: ≥ 20 ký tự, nói rõ **thấy gì trong ảnh** (vd: "ghế tựa gỗ một chỗ ngồi, detection ghi bench, panoptic ghi chair đúng"). Không ghi chung chung "có lỗi"/"OK". Không chép ghi chú của người khác.
- Ứng viên lệch lớp (cột `type` để trống): nhìn vật thật là gì. Detection sai → `class_swap`; panoptic sai → `category_swap`. Chỉ ghi **một** loại.
- `bbox_drift`: box đỏ có lệch khỏi vật không? Nếu segment xanh phủ **hai vật riêng** thì có thể là gộp (báo N1), không phải lệch box.

| Người | File | Ảnh | Ứng viên | Lý do validator nêu |
|---|---|---|---|---|
| N1 Võ Duy Thanh | `r6475_N1.csv` | [000000007795](r6475_img/006_000000007795_instance_merge.jpg) | instance_merge | segment 7435899 'bed' (89363 px) trải trên 2 box 'bed': box #0 chứa 98%, box #1 chứa 32%. Box thừa không có segment riêng |
| N1 Võ Duy Thanh | `r6475_N1.csv` | [000000021903](r6475_img/008_000000021903_bbox_drift.jpg) | bbox_drift | segment 10659243 'person' bbox [334, 224, 640, 475] tràn 89 px ra ngoài box [334, 224, 551, 475] (35% cạnh ngắn; tự nhiên <= 2 px); box chứa 92% pixel của segment |
| N2 Đinh Đức Hiếu | `r6475_N2.csv` | [000000000785](r6475_img/001_000000000785_missing_box.jpg) | missing_box | segment 3287629 'person' chiếm 27486 px (10.1% ảnh), không box 'person' nào phủ (cao nhất 0%) |
| N2 Đinh Đức Hiếu | `r6475_N2.csv` | [000000005001](r6475_img/004_000000005001_bbox_drift.jpg) | bbox_drift | segment 5919587 'person' bbox [209, 61, 298, 209] tràn 13 px ra ngoài box [195, 47, 285, 196] (14% cạnh ngắn; tự nhiên <= 2 px); box chứa 93% pixel của segment |
| N3 Nguyễn Hoài Nam | `r6475_N3.csv` | [000000017436](r6475_img/002_000000017436_class_swap-category_swap.jpg) | class_swap|category_swap | box #1 detection ghi 'bench', segment 4017234 panoptic ghi 'chair', trùng vị trí (IoU 0.99, 100% pixel trong box) |
| N4 Nguyễn Minh Hiếu | `r6475_N4.csv` | [000000022589](r6475_img/003_000000022589_class_swap-category_swap.jpg) | class_swap|category_swap | box #0 detection ghi 'horse', segment 6189719 panoptic ghi 'sheep', trùng vị trí (IoU 0.994, 100% pixel trong box) |
| N5 Bùi Anh Dũng | `r6475_N5.csv` | [000000007784](r6475_img/005_000000007784_bbox_drift.jpg) | bbox_drift | segment 8881844 'kite' bbox [94, 86, 334, 306] tràn 43 px ra ngoài box [51, 100, 291, 320] (19% cạnh ngắn; tự nhiên <= 2 px); box chứa 80% pixel của segment |
| N6 Trần Quang Nam | `r6475_N6.csv` | [000000018737](r6475_img/007_000000018737_bbox_drift.jpg) | bbox_drift | segment 5919584 'motorcycle' bbox [254, 159, 592, 408] tràn 45 px ra ngoài box [299, 152, 640, 403] (18% cạnh ngắn; tự nhiên <= 2 px); box chứa 92% pixel của segment |

Lệnh (sau `git pull`):
```
git add review_parts/r6475_N<số>.csv
git commit -m "P2: review anh r6475 (N<số>)"
git push
```
