# Day 10 — Bàn giao dataset và truy vết

Lab chạy trên một repo này. Python 3.10 trở lên, chỉ thư viện chuẩn. Không cần repo chấm riêng và không cần cài thêm gói.

Mục tiêu là phát hành một lô ảnh có kiểm soát: biết lô đang giữ lỗi gì, quyết định có được đưa đi train hay không, và khi đã train rồi mới phát hiện lỗi thì chỉ ra training run nào bị ảnh hưởng.

Bộ ảnh của lab là 500 ảnh COCO val2017, không dùng để đo model. Cùng 500 ảnh có nhãn detection và mask panoptic. Injector tạo delivery và ground truth. Nhóm tự viết chương trình bắt lỗi, ghi ra cùng format, rồi `score_findings.py` so hai danh sách.

## 1. Cuối buổi phải có gì

Mỗi nhóm nộp:

1. Script của nhóm đọc `delivery/` và ghi `errors.json`. Không đọc `_private/truth.json`.
2. `runs/s<seed>/report.md` và `runs/p<seed>/report.md` do `score_findings.py` in ra cho đúng seed giảng viên.
3. `runs/s<seed>/errors.json` và `runs/p<seed>/errors.json` đã dùng để chấm.
4. Kết quả `impact` cho release detection: training run `R-021` có bị ảnh hưởng hay không.
5. Commit riêng của từng người trong nhóm 5–6 người.

Repo không có sẵn bộ bắt lỗi. Điểm chỉ ra từ danh sách nhóm nộp so với ground truth của seed.

## 2. Cái gì đã được cấp

Chạy mọi lệnh từ thư mục gốc của repo.

| File | Việc nó làm | Nhóm có sửa không |
|---|---|---|
| `scripts/download_public.py` | Tải 500 ảnh COCO val2017, nhãn detection và mask panoptic | Không cần |
| `scripts/inject_faults.py` | Gài lỗi detection và ghi ground truth | Không sửa |
| `scripts/inject_panoptic.py` | Gài lỗi panoptic và ghi ground truth | Không sửa |
| `scripts/score_findings.py` | So `errors.json` với ground truth, ghi `report.md` | Không sửa |
| `scripts/metrics.py` | Công thức precision, recall, F1 | Không sửa |
| `scripts/run_lab.py` | Gọi hai injector cho các seed, không chấm | Không cần |
| `scripts/lineage.py` | Ghi `runs/lineage.jsonl` và trả lời run nào dùng một release | Không cần |
| `tests/test_pipeline.py` | Kiểm tra injector và thước chấm trên ảnh giả | Chạy, không cần sửa |
| `examples/errors.sample.json` | Danh sách lỗi giả, đúng format `errors`, target không khớp seed nào | Copy vào run để thử chấm |
| `examples/report.sample.md` | Report của file giả khi chấm với seed `93751` | Chỉ xem |

`.gitignore` bỏ qua `data_source/`, `runs/`, file zip và `__pycache__/`. Những thư mục này tạo trên máy, không commit.

## 3. Dữ liệu

Một lần có mạng:

```bash
python scripts/download_public.py --dataset coco500
```

Lần tải đầu cần khoảng 1,1 GB cache rồi giữ lại 500 ảnh. Script tải annotation COCO chính thức, chọn 500 id, tải đúng 500 file jpg, và rút đúng 500 mask từ zip panoptic. Lần sau đã đủ file thì không tải lại. Zip cache nằm ở `data_source/cache/`.

Quy tắc chọn, ghi trong `data_source/coco500/selection.json`: ảnh val2017 có ít nhất một box không phải crowd và có annotation panoptic, sắp theo `image_id` tăng dần, lấy 500 ảnh đầu. Không dùng seed. Mọi máy chạy lệnh này ra cùng 500 ảnh.

Nguồn: [COCO download](https://cocodataset.org/#download). Quyền ảnh: [COCO terms of use](https://cocodataset.org/dataset/termsofuse.htm). Annotation COCO dùng CC BY 4.0.

Detection, thư mục injector đọc:

```text
data_source/coco500/images/train2017/*.jpg
data_source/coco500/labels/train2017/*.txt
```

Tên thư mục `train2017` chỉ để injector tìm đúng chỗ. Ảnh thực tế là val2017. Nhãn là YOLO, một dòng một box: `class_id x_center y_center width height`, tọa độ chuẩn hóa 0 đến 1. `class_id` là 0 đến 79 theo đúng 80 lớp instance của COCO, không phải `category_id` gốc. Box bị kẹp vào trong ảnh lúc chuyển đổi, nên lô chưa gài lỗi không có box tràn sẵn.

Panoptic, `scripts/inject_panoptic.py` đọc:

```text
data_source/coco_panoptic500/images/          # cùng 500 ảnh
data_source/coco_panoptic500/masks/*.png      # mask panoptic, id segment mã hóa bằng màu
data_source/coco_panoptic500/panoptic.json    # categories, images, annotations của 500 ảnh
```

`panoptic.json` giữ format COCO panoptic. Mỗi annotation có `segments_info` với `id`, `category_id`, `area`, `bbox`, `iscrowd`. Pixel của mask có mã `R + G * 256 + B * 256^2` bằng `segments_info.id`.

`--dataset coco128` vẫn tải bộ 128 ảnh cũ của Ultralytics để thử máy yếu. Injector mặc định không đọc bộ đó. Muốn dùng thì truyền `--source data_source/coco128`.

`scene_id` không có trong COCO. Injector tự gán: ảnh được sắp theo tên, mỗi 8 ảnh một nhóm `simulated_group_000`, `simulated_group_001`, ... Nhóm chẵn gán `split: train`, nhóm lẻ gán `split: val`. Mọi ảnh bắt đầu với `guideline_version: v1.3`.

## 4. Một seed tạo ra gì

Mọi lựa chọn ngẫu nhiên đi qua `random.Random(seed)`. Cùng `--seed`, cùng `--fault-count`, cùng bộ 500 ảnh thì ra cùng `delivery/` và cùng ground truth.

Với `--fault-count 8` (mặc định của bài test), mỗi seed chứa đúng một lần mỗi loại lỗi trong mục 5. Seed chỉ đổi ảnh nào hoặc scene nào bị gài lỗi nào, không đổi danh sách loại lỗi. `--fault-count 0` không gài lỗi. `--fault-count` lớn hơn 8 thì các lỗi dư được rút thêm từ 8 loại, có thể trùng loại trên hai ảnh khác nhau.

Lệnh tách, khi cần nhìn một seed:

```bash
python scripts/inject_faults.py --seed 11 --out runs/s11 --dev-truth
```

`--dev-truth` chỉ in danh sách lỗi ra terminal. Dù có flag này hay không, ground truth vẫn được ghi tại `runs/s11/_private/truth.json`. Validator không được nhận đường dẫn đó.

`--out` đã tồn tại thì bị xóa rồi tạo lại.

### Thư mục delivery

```text
runs/s11/delivery/
  images/                 # ảnh được giao; ảnh missing_image không còn file
  labels/                 # nhãn YOLO, một file .txt cho mỗi ảnh
  manifest.json           # danh sách file, đường dẫn, SHA-256
  metadata.json           # scene_id, split, guideline_version
  release.json            # release_id công khai
runs/s11/_private/
  truth.json              # ground truth; script bắt lỗi không được đọc
runs/s11/errors.json      # danh sách nhóm nộp, cùng format với truth.errors
runs/s11/metrics.json     # do score_findings.py ghi
runs/s11/report.md
```

`manifest.json`:

```json
{
  "dataset": "COCO128",
  "num_classes": 80,
  "guideline": "v1.3",
  "items": {
    "000000000009": {
      "image": "images/000000000009.jpg",
      "label": "labels/000000000009.txt",
      "image_sha256": "64 ký tự hex"
    }
  }
}
```

`metadata.json` có `items[].image_id`, `scene_id`, `split`, `guideline_version`.

`release_id` có dạng `coco500_` cộng 12 ký tự hex đầu của SHA-256 ghép bytes của `manifest.json` và `metadata.json`. Cùng delivery thì cùng `release_id`. Id này không chứa seed.

`truth.json`:

```json
{
  "seed": 11,
  "task": "detection",
  "errors": [
    {"type": "scene_leak", "target": "simulated_group_000", "unit": "scene"}
  ]
}
```

## 5. Tám lỗi được gài

Đơn vị chấm là cặp `(type, target)`. `scene_leak` có target là `scene_id`. Bảy loại kia có target là tên ảnh, không có đuôi `.jpg`.

| Loại | Việc injector làm | Nhìn delivery có thấy không |
|---|---|---|
| `missing_image` | Xóa file jpg, để lại file nhãn và dòng trong manifest | Có. File ảnh không tồn tại |
| `wrong_hash` | Giữ nguyên file, ghi `image_sha256` thành 64 số 0 | Có. SHA-256 file khác manifest |
| `invalid_class` | Đổi class của box đầu thành `99` | Có. 99 nằm ngoài 0..79 |
| `bbox_out_of_bounds` | Đổi tâm x của box đầu thành `1.2` | Có. Box không nằm trong ảnh |
| `bbox_drift` | Dịch tâm x khoảng 5%, box vẫn nằm trong ảnh | Không, nếu chỉ nhìn file được giao. Box vẫn hợp lệ. Cần đối chiếu nhãn gốc |
| `class_swap` | Đổi class thành `(class + 1) % 80`, class mới vẫn hợp lệ | Không, nếu chỉ nhìn file được giao. Cần đối chiếu nhãn gốc |
| `scene_leak` | Đổi `split` của một ảnh sang phía còn lại, nên một `scene_id` có cả train và val | Có. Metadata của scene không còn một split |
| `guideline_mismatch` | Đổi `guideline_version` của một ảnh thành `v1.2` trong khi manifest là `v1.3` | Có. Metadata lệch guideline của manifest |

Hai nhóm điểm, không gộp thành một F1:

| Nhóm | Loại |
|---|---|
| `rule_detectable` | Detection: `missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `scene_leak`, `guideline_mismatch`. Panoptic: `invalid_category_id`, `thing_overlap` |
| `reference_or_review` | Detection: `bbox_drift`, `class_swap`. Panoptic: `category_swap`, `instance_merge` |

Ảnh gốc trước khi gài lỗi nằm ở `data_source/coco500` và `data_source/coco_panoptic500`. Đối chiếu với hai thư mục đó là cách hợp lệ để thấy lỗi gán nhãn. Validator không được mở `_private/truth.json`.

`inject_faults.py` chỉ ghi một lỗi vào ground truth khi file hoặc metadata thật sự đổi. Box quá sát mép, dịch 5% mà làm tròn vẫn ra cùng số, thì ảnh đó không được chọn. Hai `scene_leak` không rơi vào cùng một `scene_id`, vì điểm là một cặp `(type, target)`, cặp trùng sẽ bị tính một lần.

## 5b. Bốn lỗi panoptic cần bắt

`inject_panoptic.py` dùng `random.Random(seed)`. `--fault-count 8` gài mỗi loại hai lần, mỗi lần một ảnh. Ground truth: `runs/p<seed>/_private/truth.json`. Validator không được đọc file này. Điểm so cặp `(type, target)`. Target là tên ảnh, không có đuôi.

| Loại | Nhóm | Lỗi trông như thế nào | Cách bắt, chỉ từ delivery |
|---|---|---|---|
| `invalid_category_id` | luật | Một vật bị gán `category_id` `9999`, không có trong `categories` của `panoptic.json`. Pixel không đổi | `category_id` không thuộc tập id trong `categories` |
| `thing_overlap` | luật | Hai vật đè nhau. Mask panoptic chỉ giữ một id trên mỗi pixel, nên một phần pixel của vật A bị tô thành id của vật B. `area` và `bbox` của A vẫn khai vùng cũ, kể cả pixel đã mất | Đếm pixel của từng `segments_info.id`. Nếu số pixel nhỏ hơn `area`, id khác đã đè lên. Không dùng riêng bbox giao nhau: hai bbox chữ nhật có thể giao nhau dù mask không đè |
| `category_swap` | nhãn gốc | Vùng pixel giữ nguyên. `category_id` đổi sang một lớp thing khác, lớp mới vẫn có trong `categories` | Không chứng minh được từ delivery một mình. So từng segment với `data_source/coco_panoptic500` |
| `instance_merge` | nhãn gốc | Hai instance cùng lớp thành một vùng. Pixel của instance nhỏ mang id của instance lớn. `area` và `bbox` của instance giữ lại được tính lại. Id cũ biến mất khỏi cả JSON và mask | File vẫn nhất quán. So số instance cùng lớp với nhãn gốc |

Dòng nộp cho một ảnh:

```json
{"errors": [{"type": "thing_overlap", "target": "000000000139"}]}
```

`thing_overlap` và `invalid_category_id` nhìn được trên delivery. `category_swap` và `instance_merge` cần so với `data_source/coco_panoptic500`. Script bắt lỗi không đọc `_private`.

## 6. Format chung và cách chấm

Ground truth và danh sách nhóm nộp dùng cùng một list. Khóa là `errors`. Mỗi phần tử có `type` và `target`. Khóa khác trên ground truth, như `unit` hoặc `segment_id`, không được tính điểm.

Ground truth, do injector ghi, nhóm không đọc khi bắt lỗi:

```json
{
  "seed": 11,
  "task": "detection",
  "errors": [
    {"type": "class_swap", "target": "000000000139", "unit": "image"}
  ]
}
```

Danh sách nhóm nộp, đặt tại `runs/s11/errors.json` hoặc `runs/p11/errors.json`:

```json
{
  "errors": [
    {"type": "class_swap", "target": "000000000139"}
  ]
}
```

`type` phải đúng tên ở mục 5 hoặc 5b. `scene_leak` có `target` là `scene_id`. Mọi loại khác có `target` là tên ảnh, không có đuôi file. Cặp trùng chỉ tính một lần.

Chấm một run:

```bash
python scripts/score_findings.py --run runs/s11
```

Chấm detection và panoptic của cùng seed, lệnh in thêm `rank recall`:

```bash
python scripts/score_findings.py --run runs/s11 --run runs/p11
```

Hoặc chỉ định hai file:

```bash
python scripts/score_findings.py --truth runs/s11/_private/truth.json --errors runs/s11/errors.json
```

Lệnh ghi `report.md` và `metrics.json` cạnh file `errors.json`. `rank recall` là trung bình recall nhóm `reference_or_review` của detection và panoptic. Nhóm đó gồm `bbox_drift`, `class_swap`, `category_swap`, `instance_merge`.

### Thử chấm bằng file mẫu

`examples/errors.sample.json` là một danh sách giả. Đúng khóa `errors`, đúng tên `type`, `target` là id bịa. File trộn cả lỗi detection và panoptic để nhìn đủ tên loại. Đây không phải đáp án của seed nào.

Tạo delivery với seed bất kỳ, copy cùng một file vào cả hai run, rồi chấm:

```bash
python scripts/run_lab.py --seeds 11
cp examples/errors.sample.json runs/s11/errors.json
cp examples/errors.sample.json runs/p11/errors.json
python scripts/score_findings.py --run runs/s11 --run runs/p11
```

Đổi `11` bằng seed khác thì ground truth đổi, điểm đổi. Lệnh chấm không đọc nội dung file mẫu theo seed. Nó chỉ so `type` và `target` với `runs/s<seed>/_private/truth.json` và `runs/p<seed>/_private/truth.json`.

`examples/report.sample.md` là output của đúng lệnh trên với seed `93751`. Mở file đó để thấy bố cục `report.md` trước khi nhóm có script bắt lỗi. Vì target trong file mẫu không trùng ground truth, report đó có TP 0. Các dòng panoptic bị tính FP khi chấm run detection, và ngược lại. Recall `1.0` ở một loại không có trong ground truth của task đó nghĩa là truth của loại đó rỗng, không có nghĩa đã bắt đúng.

Khi nhóm viết script riêng, detection chỉ ghi loại của mục 5 vào `runs/s<seed>/errors.json`, panoptic chỉ ghi loại của mục 5b vào `runs/p<seed>/errors.json`.

Quyết định in trong báo cáo chỉ nhìn danh sách nộp:

- `HOLD` khi danh sách có ít nhất một lỗi thuộc các loại đã biết.
- `RELEASE_CANDIDATE` khi danh sách rỗng. Danh sách rỗng trên một lô có lỗi nghĩa là recall 0.

Điểm chỉ tính trên run có ground truth khác rỗng. Sửa một delivery tạo bằng `--fault-count 0`, hoặc nộp `errors.json` cho delivery đó, không đổi `rank recall` của seed. Ảnh và nhãn trước khi gài lỗi nằm ở `data_source/coco500` và `data_source/coco_panoptic500`.

## 7. Việc nhóm làm trong buổi

```bash
python scripts/download_public.py --dataset coco500
python scripts/run_lab.py --seeds 11,22,33
```

Lệnh này chỉ tạo `runs/s<seed>/delivery`, `runs/p<seed>/delivery` và `_private/truth.json`. Chưa có điểm.

Nhóm viết script đọc delivery, ghi `errors.json` đúng format mục 6, rồi:

```bash
python scripts/score_findings.py --run runs/s11 --run runs/p11
```

Nhóm được chọn seed khác để thử:

```bash
python scripts/run_lab.py --seeds 7,100,2026
```

`run_lab.py` ghi đè thư mục run nhưng nối thêm `runs/lineage.jsonl`. Trước một lượt sạch, xóa `runs/`.

Seed đầu tiên được gắn training run `R-021`. `score_findings.py` không ghi lineage. Muốn thấy run bị ảnh hưởng, ghi quyết định HOLD cho đúng `release_id` trong `runs/s<seed>/delivery/release.json`, rồi hỏi impact:

```bash
python scripts/lineage.py record --event decision --release-id coco500_xxxxxxxxxxxx --decision HOLD
python scripts/lineage.py impact --release-id coco500_xxxxxxxxxxxx
```

Dòng mong đợi là `R-021: affected=True action=review_or_retrain`. Chưa ghi HOLD thì dòng đó là `affected=False`. Giữ release cũ, không ghi đè, làm bản sửa, rồi train lại. Đổi dataset không tự sửa model đã học.

## 8. Cách đọc số

| Số | Cách tính |
|---|---|
| TP | Cặp có trong ground truth và trong `errors.json` |
| FP | Cặp có trong `errors.json` nhưng không có trong ground truth |
| FN | Cặp có trong ground truth nhưng không có trong `errors.json` |
| precision | TP / (TP + FP). Cả hai list rỗng thì precision = 1. List nộp rỗng nhưng truth còn lỗi thì precision ghi `—` |
| recall | TP / (TP + FN). Truth của nhóm đó rỗng thì recall = 1 |
| F1 | Trung bình điều hòa của precision và recall. Precision là `—` thì F1 là `—` |

Bảng trong `report.md` tách `rule_detectable` và `reference_or_review`. Một F1 tổng có thể cao khi nhóm chỉ bắt lỗi luật và bỏ lỗi gán nhãn.

## 9. Bài test cuối giờ

Giảng viên đưa một số, ví dụ `93751`. Cả lớp dùng đúng số đó và `--fault-count 8`.

```bash
rm -rf runs
python scripts/run_lab.py --seeds 93751
```

Script của nhóm ghi `runs/s93751/errors.json` và `runs/p93751/errors.json`, rồi:

```bash
python scripts/score_findings.py --run runs/s93751 --run runs/p93751
python scripts/lineage.py record --event decision --release-id <release_id trong runs/s93751/delivery/release.json> --decision HOLD
python scripts/lineage.py impact --release-id <release_id trong runs/s93751/delivery/release.json>
```

Nộp hai `report.md`, hai `errors.json`, và dòng `rank recall`. Giảng viên chạy lại injector cùng seed rồi chạy `score_findings.py` trên file của nhóm. Cùng seed ra cùng ground truth. `rank recall` cao hơn thì đứng trên. Số đó không đọc delivery nào khác ngoài hai run của seed.

## 10. Lệnh lẻ

```bash
python scripts/inject_faults.py --seed 11 --fault-count 8 --out runs/s11 --dev-truth
python scripts/inject_panoptic.py --seed 11 --fault-count 8 --out runs/p11 --dev-truth
python scripts/score_findings.py --run runs/s11 --run runs/p11
```

`--dev-truth` in list `errors` ra terminal. File truth vẫn được ghi dù không có flag.

```bash
python -m unittest tests/test_pipeline.py
```

## 11. Việc không được làm

- Sửa `inject_faults.py` hoặc `inject_panoptic.py` trước bài test. Seed chỉ có một nghĩa khi injector không đổi.
- Sửa `metrics.py` hoặc `score_findings.py` để đổi điểm.
- Để script bắt lỗi đọc `_private/truth.json`.
- Gộp hai nhóm recall thành một số rồi báo đã bắt 100% lỗi.
