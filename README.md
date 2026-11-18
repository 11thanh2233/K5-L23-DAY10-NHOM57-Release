# Day 10 — Bàn giao dataset và truy vết

Python 3.10 trở lên, chỉ thư viện chuẩn. Không cần cài thêm gói, không cần GPU.

Nhóm nhận một lô nhãn 250 ảnh (detection + panoptic) có lỗi. Việc của nhóm là **bắt lỗi, quyết định có cho train hay không, bàn giao một bản sửa không ghi đè bản cũ, và truy vết được ảnh nào, ai cần sửa** khi team AI báo lỗi.

Lỗi của bài chia hai loại:
- **Lỗi luật:** nhìn file giao là thấy, nên viết script bắt được.
- **Lỗi gán nhãn:** file vẫn hợp lệ, và lô **không có nhãn gốc** để so. Chỉ thấy khi đối chiếu detection với panoptic của cùng ảnh, rồi **mở ảnh ra xem** để biết bên nào sai.

Điểm xếp hạng là F1, nên báo thừa bị trừ như bỏ sót.

## 1. Cuối buổi phải có gì

Mỗi nhóm nộp:

1. `validator/`: script của nhóm, đọc **chỉ** thư mục `delivery/` và ghi danh sách lỗi.
2. Với seed luyện tập của nhóm, trong `runs/r<seed>/`: `errors.json`, `review_log.csv`, `trace.json`, `security.md`, thư mục `handover/<release_id>_v2/` + `.zip` + `.sha256`, và `runs/lineage.jsonl`. `check_handover.py` phải không còn FAIL.
3. Với **đề ẩn** phát cuối buổi: `errors.json`, `review_log.csv`, `trace.json`.
4. Commit riêng của từng người trong nhóm.

## 2. Dữ liệu

Chạy một lần khi có mạng:

```bash
python scripts/download_public.py
```

Lệnh tải annotation COCO chính thức (khoảng 1 GB, giữ trong `data_source/cache/`) rồi tải 250 ảnh song song. Quy tắc chọn ảnh: ảnh val2017 có ít nhất một box không phải crowd và có panoptic, sắp theo id, lấy 250 ảnh đầu. Mọi máy ra cùng 250 ảnh. Nguồn: [COCO](https://cocodataset.org/#download), quyền ảnh: [COCO terms of use](https://cocodataset.org/dataset/termsofuse.htm), annotation CC BY 4.0.

`data_source/` là nguồn để **tạo** lô. Validator **không được đọc** `data_source/`: đề ẩn cuối buổi dùng 250 ảnh khác, tên ảnh đã mã hoá, file đã ghi lại. Script nào dựa vào nhãn gốc sẽ không tìm được gì để so.

## 3. Một lô gồm gì

```bash
python scripts/run_lab.py --seeds 11        # tạo runs/r11, gắn training run R-021 vào seed đầu
```

```text
runs/r11/delivery/
  images/*.jpg              # ảnh (có thể thiếu file)
  labels/*.txt              # nhãn YOLO: class_id x_center y_center width height (chuẩn hoá 0-1)
  masks/*.png               # mask panoptic, id segment = R + G*256 + B*256^2
  panoptic.json             # categories, images, annotations (segments_info: id, category_id, area, bbox, iscrowd)
  classes.txt               # 80 lớp detection: "class_id tên"
  manifest.json             # mỗi ảnh: đường dẫn image/label/mask và sha256 của từng file
  metadata.json             # mỗi ảnh: scene_id, split, job_id, guideline_version
  jobs.csv                  # job_id, annotator, reviewer, guideline (phiên bản ghi ở đầu job)
  guideline/changelog.md    # v1.2 → v1.3 đổi quy tắc của một lớp
  incoming/ticket.md        # team AI báo lỗi sau khi train
  release.json              # release_id của lô v1
runs/r11/_private/          # ground truth: validator KHÔNG đọc
runs/lineage.jsonl          # nhật ký lineage
```

`scene_id`, job, người gán và người kiểm là **giả lập** cho bài, không có trong COCO. Một cảnh là 5 ảnh liên tiếp; một job là 25 ảnh. Các job đầu theo guideline v1.2, các job sau theo v1.3.

## 4. Các loại lỗi

Đơn vị chấm là cặp `(type, target)`. `scene_leak` có target là `scene_id`; mọi loại khác có target là tên ảnh, không có đuôi. **Số lỗi mỗi loại thay đổi theo seed (có loại có thể vắng)**, và mỗi ảnh mang nhiều nhất một lỗi.

| Nhóm | Loại | Nghĩa |
|---|---|---|
| Luật (detection) | `missing_image` | manifest có ảnh nhưng thiếu file |
| | `wrong_hash` | sha256 ghi trong manifest không phải của file đó |
| | `invalid_class` | class_id ngoài 0–79 |
| | `bbox_out_of_bounds` | box vượt ra ngoài ảnh |
| | `duplicate_box` | một vật được gán hai box gần như trùng nhau |
| | `scene_leak` | một cảnh có ảnh ở cả train và val |
| | `guideline_mismatch` | guideline của ảnh khác guideline ghi ở job của nó |
| Luật (panoptic) | `invalid_category_id` | category_id không có trong `categories` |
| | `thing_overlap` | `area` khai nhiều hơn số pixel thật của segment (bị vật khác đè) |
| Gán nhãn | `class_swap` | box detection bị gán nhầm sang lớp dễ nhầm |
| | `bbox_drift` | box detection bị lệch khỏi vật |
| | `missing_box` | detection thiếu box cho một vật đáng kể |
| | `category_swap` | segment panoptic bị gán nhầm lớp dễ nhầm |
| | `instance_merge` | hai vật cùng lớp bị gộp thành một segment |

Lỗi gán nhãn **không chứng minh được bằng một file**. Gợi ý cách làm:
- Ghép box detection với segment panoptic của cùng ảnh.
- Lệch lớp, lệch vị trí, hoặc số vật không khớp là **ứng viên**.
- COCO tự nhiên đã có lệch giữa hai nguồn (vật bị che, crowd), nên **không phải ứng viên nào cũng là lỗi**.
- Mở ảnh ra xem và ghi kết luận vào `review_log.csv`. Khi detection và panoptic bất đồng về lớp, chính ảnh cho biết bên nào sai (`class_swap` hay `category_swap`).

## 5. Quy trình trong buổi

**P1. Bắt lỗi luật.** Viết `validator/`: đọc `delivery/`, ghi `errors.json` theo mẫu `examples/errors.sample.json`. Thử trên vài seed:

```bash
python scripts/run_lab.py --seeds 11,22
python scripts/score_findings.py --run runs/r11
```

**P2. Đối chiếu và xem ảnh.** Validator ghi thêm danh sách ứng viên. Nhóm chia nhau mở ảnh và ghi `review_log.csv` (`image,type,verdict,note`, với verdict là `confirmed` hoặc `rejected`; mẫu ở `templates/`). Chỉ đưa vào `errors.json` lỗi gán nhãn đã `confirmed`.

**P3. Quyết định và lineage.** Tỉ lệ lỗi = số ảnh (hoặc cảnh) trong `errors.json` / 250. Theo ngưỡng Day 7: trên 2% thì v1 không được Release. Ghi quyết định rồi hỏi training run nào bị ảnh hưởng:

```bash
python scripts/lineage.py record --event decision --release-id <release_id v1> --decision HOLD
python scripts/lineage.py impact --release-id <release_id v1>        # R-021: affected=True action=review_or_retrain
```

**P4. Bàn giao v2, không ghi đè v1.** Tạo `runs/r<seed>/handover/<release_id>_v2/`:

| Phần | Nội dung |
|---|---|
| `images/`, `labels/` | ảnh và nhãn **giữ nguyên** của v1, trừ ảnh phải gán lại |
| `rework_queue.csv` | `image,type,annotator,reviewer,action`: ảnh tách ra để gán lại, giao đúng người theo `jobs.csv` |
| `manifest.csv` | `file,sha256` cho mọi file trong `images/` và `labels/` |
| `label_summary.csv` | `class,count` theo tên lớp, dòng cuối `TOTAL` |
| `truyvet.csv` | `image,scene_id,split,job_id,annotator,reviewer,guideline`: guideline theo **job**, mỗi cảnh một split |
| `README.txt` | mẫu `templates/README.txt`: số ảnh, số nhãn, QC v1 có mẫu số, kết luận v1 và v2 |

Lỗi `wrong_hash`, `guideline_mismatch`, `scene_leak` sửa được ngay trong v2 (hash mới, guideline theo job, đưa cả cảnh về một split). Các lỗi khác cần gán lại nên vào `rework_queue`. Sau đó:

```bash
python scripts/pack_release.py runs/r11/handover/<release_id>_v2
python scripts/lineage.py record --event release --release-id <release_id>_v2 --parent <release_id>
python scripts/check_handover.py --run runs/r11
```

**P5. Truy vết ticket.** Đọc `incoming/ticket.md` và `guideline/changelog.md`, rồi ghi `trace.json` (mẫu ở `templates/`):
- `tier_a`: ảnh trong các cảnh team AI nêu, thuộc job guideline cũ, có lớp bị đổi quy tắc.
- `tier_b`: các ảnh khác cùng điều kiện, chưa ai báo.
- `notify`: người gán và người kiểm của các job đó.

**P6. Bảo mật.** Điền `security.md` theo mẫu: ca USB, năm việc được/không, ca khuôn mặt (kết luận Hold). COCO có ảnh người thật.

## 6. Bài test cuối giờ (đề ẩn)

Giảng viên phát `delivery/` của một seed bí mật, lấy từ 250 ảnh **khác** bộ luyện tập, tên ảnh dạng `img_0001`. Nhóm có 40 phút: chạy validator, xem ảnh ứng viên, nộp `errors.json`, `review_log.csv` và `trace.json`. Giảng viên chấm:

```bash
python scripts/score_findings.py --run <thư mục nộp của nhóm> --truth-dir <đề ẩn>/_private
```

Giảng viên tạo đề ẩn bằng:

```bash
python scripts/download_public.py --pool test
python scripts/inject_release.py --seed <bí mật> --pool test --opaque --out hidden/r<seed>
```

## 7. Chấm điểm (100)

| Phần | Điểm | Cách chấm |
|---|---:|---|
| Đề ẩn: bắt lỗi | 40 | theo `rank F1` của `score_findings.py`, xếp hạng giữa các nhóm |
| Đề ẩn: truy vết | 10 | F1 của `tier_a`, `tier_b`, `notify` |
| Bàn giao v2 trên seed luyện tập | 25 | `check_handover.py` không FAIL + người chấm đọc README, rework_queue |
| Review bằng mắt | 10 | `review_log.csv` có ghi chú cụ thể; lỗi gán nhãn nào cũng có dòng confirmed |
| Bảo mật | 5 | `security.md` gắn với lô vừa làm |
| Vấn đáp | 10 | mỗi người giải thích một đoạn validator và một quyết định trong review_log |

Tham khảo khi giảng viên thử: chỉ kiểm luật được F1 khoảng 0,7. Báo hết ứng viên mà không xem ảnh được F1 khoảng 0,6 (tệ hơn, vì báo thừa). Đối chiếu đúng cộng xem ảnh cẩn thận được F1 trên 0,9.

## 8. Cách đọc số

| Số | Cách tính |
|---|---|
| TP / FP / FN | cặp đúng / cặp báo thừa / cặp bỏ sót |
| precision | TP / (TP + FP) |
| recall | TP / (TP + FN) |
| F1 | trung bình điều hoà của precision và recall |

Report tách `rule_detectable` và `cross_check_review`. F1 cao chỉ nhờ lỗi luật không có nghĩa là lô đã được kiểm.

## 9. Lệnh lẻ

```bash
python scripts/inject_release.py --seed 11 --out runs/r11 --dev-truth   # in ground truth: chỉ để gỡ lỗi
python scripts/inject_release.py --seed 5 --no-faults --out runs/clean  # lô sạch: đo nhiễu tự nhiên giữa detection và panoptic
python -m unittest discover -s tests
```

## 10. Việc không được làm

- Validator đọc `_private/`, `data_source/`, annotation COCO hoặc tải gì từ mạng.
- Sửa `inject_release.py`, `metrics.py`, `score_findings.py`, `check_handover.py`.
- Sửa file trong `delivery/` (v1). Bản sửa là v2.
- Đưa lỗi gán nhãn vào `errors.json` mà không có dòng `confirmed` trong `review_log.csv`.
- Gộp hai nhóm điểm thành một số rồi báo đã bắt 100% lỗi.
