# Nhóm VoDuyThanh

- Nhóm trưởng: Võ Duy Thanh (2A202603211)
- Seed luyện tập: 6475 (lô v1 `lab250_9b6266dd5aa0`, gắn training run R-021)
- Repo: https://github.com/11thanh2233/K5-L23-DAY10-VoDuyThanh-Release

> Mỗi người: chọn một dòng Người 2–6, tự điền họ tên, MSHV, tài khoản GitHub, rồi tự commit bằng tài khoản của mình
> (`git config user.name` / `user.email` là của bạn). Mỗi người cần ít nhất 2 commit có nội dung.

| # | Họ và tên | MSHV | Tài khoản GitHub | Phần chính |
|---|---|---|---|---|
| 1 | Võ Duy Thanh (nhóm trưởng) | 2A202603211 | 11thanh2233 | Khung `validator/validate.py`; lỗi luật mức file: `missing_image`, `wrong_hash`, `scene_leak`, `guideline_mismatch`; ghép code, gộp `errors.json`, export và nộp bài |
| 2 | Đinh Đức Hiếu | 2A202603327 | hieudd04268 | Lỗi luật nhãn: `invalid_class`, `bbox_out_of_bounds`, `duplicate_box` (detection); `invalid_category_id`, `thing_overlap` (panoptic); thử trên seed phụ và lô sạch |
| 3 | Nguyễn Hoài Nam | 2A202603186 | NamhocFPT | Đối chiếu detection ↔ panoptic (ghép theo tên lớp, IoU, pixel mask); ứng viên `class_swap`, `category_swap`, `missing_box` |
| 4 | <<Người 4>> | <<>> | <<>> | Ứng viên `bbox_drift`, `instance_merge`; đo ứng viên trên lô sạch để chọn ngưỡng; công cụ xem ảnh (vẽ box + viền segment) |
| 5 | Bùi Anh Dũng | 2A202603033 | Bui1234 | Pha 3–4: lineage (HOLD v1, release v2), lô v2 (`rework_queue`, `manifest`, `label_summary`, `truyvet`, `README.txt`), `pack_release`, `check_handover` |
| 6 | Trần Quang Nam | 2A202603118 | trannam229 | Pha 5–6: `trace.json`, `security.md`; viết `REPORT.md` và `prompts.md` |

## Việc chung

- **Pha 2 (xem ảnh):** chia đều hàng đợi ứng viên cho cả 6 người; mỗi dòng `review_log.csv` ghi rõ đã thấy gì.
- **Đề ẩn (40'):** Người 1 chạy validator · Người 3, 4 chia nhau xem ứng viên · Người 2 soát lỗi luật · Người 6 làm `trace.json` · Người 5 gộp, commit, push.

## Gợi ý commit

| # | Commit 1 | Commit 2 |
|---|---|---|
| 1 | P0 + khung validator | Gộp `errors.json`, export, nộp |
| 2 | Luật detection | Luật panoptic + kết quả nhiều seed |
| 3 | Hàm ghép + ứng viên lệch lớp | Ứng viên `missing_box` |
| 4 | Ứng viên drift/merge + đo lô sạch | Công cụ xem ảnh |
| 5 | Dựng lô v2 | v2 qua `check_handover` + lineage |
| 6 | Truy vết + bảo mật | REPORT + prompts |
