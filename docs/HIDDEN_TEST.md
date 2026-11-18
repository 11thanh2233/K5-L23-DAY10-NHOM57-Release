# Đề ẩn cuối buổi (giảng viên)

Đề ẩn dùng **250 ảnh khác** bộ luyện tập (`--pool test`), tên ảnh dạng `img_NNNN`. Image id và segment id được đánh số lại; byte ảnh và mask được ghi lại nên **không trùng hash** với file COCO. Validator nào dựa vào nhãn gốc sẽ không có gì để so.

## Chuẩn bị (trước buổi)

```bash
python scripts/download_public.py --pool test
python scripts/inject_release.py --seed <số bí mật> --pool test --opaque --out hidden/r<seed>
```

`hidden/` đã nằm trong `.gitignore`. Chỉ phát **`hidden/r<seed>/delivery/`** (nén zip), **không** phát `_private/`.

## Trong buổi (40 phút)

Phát zip `delivery/` cho các nhóm. Nhóm chạy validator, xem ảnh ứng viên, rồi nộp `submission/de_an/` gồm `errors.json`, `candidates.json`, `review_log.csv`, `trace.json`.

## Chấm

```bash
python scripts/score_findings.py --run <repo nhóm>/submission/de_an --truth-dir hidden/r<seed>/_private
```

Lệnh ghi `report.md` và `metrics.json` vào thư mục nộp. Xếp hạng theo `rank F1`; điểm theo [RUBRIC.md](../RUBRIC.md) mục 1, 2 và 4.

Kiểm phần bàn giao trên seed luyện tập của nhóm:

```bash
python scripts/export_submission.py --import <repo nhóm>/submission/r<seed>
python scripts/check_handover.py --run runs/r<seed>
```

`--import` tạo lại lô của seed đó (cùng seed thì ra cùng lô) rồi chép bài của nhóm vào. Chạy bằng bản `scripts/` **gốc** của giảng viên, không dùng bản trong repo nhóm.

## Tham khảo độ khó (giảng viên đã thử trên seed 93751)

| Cách làm | F1 đề ẩn |
|---|---|
| Diff với nhãn gốc | 0 (không ảnh nào khớp tên) |
| Chỉ kiểm luật | 0,72 |
| Báo hết ứng viên, không xem ảnh | 0,63 |
| Đối chiếu + xem ảnh đúng | 0,98 |

Hàng đợi xem ảnh trên đề ẩn khoảng 27 ảnh. Bước "xem ảnh" trong bảng được mô phỏng bằng đáp án; thời gian thật của một nhóm chưa được đo.
