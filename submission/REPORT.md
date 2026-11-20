# Báo cáo nhóm 57

Seed luyện tập **6475**, lô v1 `lab250_9b6266dd5aa0`. Mọi số dưới đây lấy từ file thật trong `runs/` (tự đo bằng `score_findings.py`, chỉ in F1 làm tròn một chữ số); không dùng `_private`, `--dev-truth` hay `--truth-dir`.

## 1. Số liệu luyện tập

**F1 theo seed** (rule / cross_check / overall):

| Seed | Chỉ lỗi luật (chưa xem ảnh) | Báo hết ứng viên, chưa xem ảnh | Sau khi xem ảnh |
|---|---|---|---|
| 6475 (seed nhóm) | 1.0 / — / 0.8 | 1.0 / 0.9 / 1.0 | **1.0 / 1.0 / 1.0** |
| 777 (`inject_release.py`) | 1.0 / — / 0.8 | 1.0 / 0.7 / 0.9 | |
| 4242 (`inject_release.py`, không dùng để chỉnh ngưỡng) | 1.0 / — / 0.8 | 1.0 / 0.8 / 0.9 | |

"Báo hết ứng viên" nghĩa là đưa mọi ứng viên vào `errors.json`; ứng viên lệch lớp chưa biết bên nào sai nên ghi cả `class_swap` lẫn `category_swap`.

**Lô sạch** (`inject_release.py --seed 5 --no-faults`, 50 ảnh pool `calib`): **0 lỗi luật, 0 ứng viên** ở ngưỡng chọn; vẫn 0 khi nới ngưỡng lệch lớp xuống IoU 0,30 / cover 0,50 và ngưỡng `missing_box` xuống 0,2% ảnh. **Hàng đợi seed 6475: 8 ảnh** (1 `missing_box`, 2 lệch lớp, 3 `bbox_drift`, 2 `instance_merge`), chia cho 6 người xem trong `review_parts/`. Quét thêm "vùng xám" sát ngưỡng trên 6475 chỉ ra thêm ảnh `000000009590` (9 segment cup, 10 box cup), giống hệt ở seed 777 và 4242 nên là lệch có sẵn của COCO, không đưa vào hàng đợi.

**Ngưỡng đã chọn và cách chọn** (đo phân bố trên lô sạch và các seed 6475, 777, 4242; ca nào lặp lại y hệt ở mọi seed là lệch tự nhiên của ảnh gốc, ca chỉ có ở một seed là lỗi gài):

| Luật / ứng viên | Ngưỡng | Căn cứ đo |
|---|---|---|
| `bbox_out_of_bounds` | tràn > 0,001 cạnh ảnh | box tự nhiên tràn 0; lỗi tràn 0,025–0,078 |
| `duplicate_box` | cùng lớp, lệch kích thước ≤ 1 px, lệch tâm ≤ 6 px | lỗi lệch tâm 1–2 px, kích thước lệch 0; cặp tự nhiên cùng kích thước gần nhất lệch tâm ~12 px. Không dùng IoU (cặp COCO tự nhiên tới IoU ~0,66) |
| `thing_overlap` | `area` khai > số pixel thật | tự nhiên lệch 0 px; lỗi lệch 1 321–8 637 px |
| Ghép box ↔ segment | cùng tên lớp, IoU ≥ 0,30 và ≥ 50% pixel segment trong box; bỏ segment crowd/stuff | pixel mask tốt hơn IoU bbox: box COCO sinh từ mask nên với cặp đúng box bọc trọn segment |
| Lệch lớp | khác lớp, IoU ≥ 0,70 và ≥ 85% pixel trong box | số ứng viên không đổi khi nới tới IoU 0,30: cặp lệch lớp tách hẳn khỏi dữ liệu tự nhiên |
| `missing_box` | segment thing ≥ 0,5% ảnh không box cùng lớp nào phủ > 30% | lô sạch 0 ứng viên ở 0,2%–1% |
| `bbox_drift` | segment tràn ra ngoài box ≥ 5 px | cặp tự nhiên tràn tối đa 2 px (làm tròn), lỗi tràn ≥ 8 px |
| `instance_merge` | box cùng lớp không có segment riêng được segment lấp đầy ≥ 25% diện tích; xét trước drift | merge thật lấp đầy box thừa 0,32–0,98; box chỉ chồng lên vì hai vật đứng sát 0,02–0,18 |

Ảnh đã có lỗi luật không sinh ứng viên gán nhãn (mỗi ảnh tối đa một lỗi): ảnh `duplicate_box` có hai box cùng lớp chứa trọn một segment, nếu không loại sẽ bị nhận nhầm là `instance_merge`.

**Kiểm độ bền** trên lô do nhóm tự tạo khó hơn mặc định (`--opaque --profile`: box lệch 6–15% thay vì 12–30%, mọi lần đổi lớp sang lớp dễ nhầm, vật nhỏ tới 0,2% ảnh, mỗi lô gài 4 lỗi một loại; seed 901, 902). F1 lỗi gán nhãn: `class_swap` 1.0/1.0, `category_swap` 1.0/1.0, `missing_box` 1.0/0.7, `bbox_drift` 0.9/1.0, `instance_merge` 1.0/1.0. Lần đo đầu, `instance_merge` chỉ 0.6/0.2 vì segment bị gộp phình ra ngoài box và bị nhận là `bbox_drift`; đổi sang tiêu chí "box thừa bị lấp đầy" và xét merge trước drift thì lên 1.0. Ca drift còn sót là box vừa lệch vừa phóng to nên vẫn bọc trọn segment: đo độ tràn không thấy, nới thêm thì đụng vật bị che tự nhiên.

**Đề ẩn** (`de_an_11.zip`, 250 ảnh `img_xxxx`): 12 lỗi luật; 12 ứng viên ở lần chạy đầu, xem ảnh được 9 confirmed, 3 rejected (box cùng lớp chỉ chồng lên vì hai vật đứng sát: `img_0013`, `img_0027`, `img_0204`). Validator sau khi sửa tiêu chí merge chỉ còn 9 ứng viên, đúng 9 ca đã xác nhận. `errors.json` nộp 21 mục.

## 2. Vì sao báo hết ứng viên làm F1 giảm?

F1 tính trên cặp (loại, ảnh): mỗi mục báo thừa làm tụt precision đúng như một mục bỏ sót làm tụt recall. Ứng viên chỉ là chỗ hai nguồn nhãn **bất đồng**; bất đồng có thể là lỗi, là lệch tự nhiên của COCO, hoặc là lỗi thật nhưng **khác loại** với loại validator đoán. Số của nhóm:

- Seed 6475: báo hết 8 ứng viên, lỗi gán nhãn ≈ **0.9**; sau khi xem ảnh ≈ **1.0**. Hai nguồn thừa: (1) hai ứng viên lệch lớp phải ghi cả `class_swap` lẫn `category_swap` vì chưa biết bên nào sai, nên chắc chắn thừa 2 mục; xem ảnh mới chọn đúng: `000000022589` là con cừu, detection ghi horse → `class_swap`; `000000017436` là băng ghế bê tông nhiều chỗ ngồi, panoptic ghi chair → `category_swap`. (2) `000000021903` validator báo `bbox_drift` (segment tràn 89 px) nhưng ảnh cho thấy box ôm vừa người cho voi ăn; phần tràn là người thứ hai ở mép phải bị gộp vào segment → thực ra là `instance_merge`. Báo theo validator là vừa thừa một mục vừa sót một mục.
- Seed 777 và 4242: báo hết cho lỗi gán nhãn ≈ 0.7 và 0.8.
- Đề ẩn: nếu báo hết 12 ứng viên ở lần chạy đầu sẽ thêm 3 mục `instance_merge` sai (`img_0013`, `img_0027`, `img_0204`: segment chỉ phủ một vật, box bên cạnh chồng lên vì vật đứng sát) cộng 4 mục thừa do ghi cả hai loại cho 4 ứng viên lệch lớp.
- Đề ẩn còn có 11 box detection nằm trên segment khác lớp (vd. chiếc ô tô làm bằng fondant trên bánh kem có cả box car và box cake; một con mèo có cả box cat và box dog). Đây là gán trùng tự nhiên: hai box khác kích thước do người gán độc lập, không phải kiểu lỗi được gài. Báo chúng là lỗi sẽ chỉ thêm báo thừa.

## 3. Quyết định và lineage

QC v1 = **21/250 = 8,4%** (13 lỗi luật + 8 lỗi gán nhãn đã xác nhận; `scene_861` tính một). Vượt ngưỡng 2% (Day 7) nên **v1 = HOLD**, ghi bằng `lineage.py record --event decision --decision HOLD`. `lineage.py impact` trả `R-021: affected=True action=review_or_retrain`.

R-021 đã train trên v1, tức đã học từ 21 ảnh lỗi: box lệch, box lặp, lớp sai (con cừu ghi horse), vật bị thiếu box. Ra lô v2 sạch hơn **không sửa được trọng số đã học**: model vẫn mang thói quen học từ nhãn sai cho tới khi train lại. Vì vậy phải đánh giá lại R-021 trên tập kiểm tra sạch, và nếu lệch thì train lại trên v2. Lineage nối ba bước: `train R-021 ← lab250_9b6266dd5aa0`, `decision HOLD`, `release lab250_9b6266dd5aa0_v2 --parent lab250_9b6266dd5aa0`; nhờ vậy khi v1 bị HOLD, `impact` tìm ra ngay run nào bị ảnh hưởng.

Lô v2: 240 ảnh, 1598 nhãn. 10 ảnh lỗi nhãn detection hoặc thiếu file sang `rework_queue.csv`, giao đúng người gán/kiểm theo `jobs.csv`. Sửa trong v2: 2 `wrong_hash` (`000000005477`, `000000020553`: mở ảnh thấy còn nguyên, đúng nội dung; manifest v1 ghi nhầm hash của ảnh khác), 1 `guideline_mismatch` (`000000015660`: `truyvet.csv` lấy guideline theo job), 1 `scene_leak` (`scene_861` đưa cả cảnh về train, split đa số của cảnh). 7 ảnh chỉ lỗi panoptic ở lại v2 vì nhãn detection vẫn đúng; ghi trong `README.txt` để báo team panoptic. `check_handover.py`: 17/17 PASS.

## 4. Hash chứng minh gì, không chứng minh gì?

**Chứng minh:** bytes của file đúng là bytes đã ghi lúc đóng gói. `manifest.csv` của v2 có sha256 của 480 file (240 ảnh + 240 nhãn); ai nhận lô tính lại sẽ biết file nào bị đổi, hỏng khi truyền hay bị thay. Zip tái lập (`pack_release.py`, thứ tự và thời gian cố định) cho cùng mã `c272adf0…199705` trên mọi máy, nên chứng minh toàn bộ lô v2 không đổi kể từ lúc chốt. `release_id` của v1 là hash của `manifest.json` + `metadata.json`, nên `check_handover` H1 chứng minh v1 không bị ghi đè; H7 chứng minh nhãn trong v2 trùng byte với nhãn v1, không ai sửa tay.

**Không chứng minh:** nhãn đúng. Hash của `000000022589.txt` khớp hoàn hảo dù nhãn ghi horse cho con cừu; hash chỉ nói file không đổi, không nói nội dung đúng. Hash cũng không chứng minh ảnh đúng nội dung hay khớp với nhãn, không chứng minh lô đủ ảnh (ảnh thiếu thì không có hash để so), không chứng minh ai đã gán. Ngược lại, hash sai chưa chắc ảnh hỏng: hai ca `wrong_hash` của lô có ảnh còn nguyên, chỉ manifest ghi sai; vì vậy phải mở ảnh kiểm trước khi quyết định sửa hash hay đưa vào rework.

## 5. Truy vết

Ticket seed 6475: model bỏ sót `truck` bị che hoặc ở mép, thấy ở `scene_166` và `scene_507`. Changelog: v1.3 bắt buộc gán box `truck` bị che > 50% hoặc cắt mép; v1.2 cho phép bỏ qua. Tiêu chí (`validator/trace_query.py`):

- **tier_a**: ảnh thuộc `scene_166` hoặc `scene_507`, nằm trong job có guideline **v1.2 theo `jobs.csv`** (J01–J03), có ít nhất một box detection lớp `truck` trong `labels/` → 2 ảnh.
- **tier_b**: các ảnh khác thoả cùng điều kiện (job v1.2, có box truck) nhưng chưa ai báo → 4 ảnh.
- **notify**: người gán và người kiểm của các job chứa ảnh tầng a, b → A01, A02, Q01, Q03.

Tự đo: tier_a 1.0, tier_b 1.0, notify 1.0. Đề ẩn dùng cùng tiêu chí (lớp `cake`, `scene_648`/`scene_719`, job v1.2 J01–J04): tier_a 2, tier_b 5, notify 5.

**Vì sao lấy guideline theo job:** guideline là quy định áp cho cả job lúc job được tạo, nên người gán làm theo phiên bản ghi ở job. Guideline ghi ở từng ảnh trong `metadata.json` có thể sai, đó chính là lỗi `guideline_mismatch` (ảnh `000000015660` của lô ghi lệch với job). Lọc theo guideline của ảnh sẽ bỏ sót hoặc kéo nhầm ảnh vào tầng a/b, và báo nhầm người.

## 6. Bug hoặc điểm chưa rõ trong lab

- `download_public.py` được thông báo bị lỗi trong lúc làm bài; nhóm làm trên bản dữ liệu đã tải ngày 19/11. `tools/build_handover.py` dựng lại lô v2 từ `errors.json` bằng một lệnh nếu dữ liệu đổi.
- File CSV lưu bằng Excel/Notepad có BOM (`﻿`) ở đầu: `csv.DictReader` đọc cột đầu thành `﻿image`, dòng review bị bỏ qua mà không báo lỗi. Nhóm đọc bằng `encoding="utf-8-sig"` khi gộp `review_parts/`. `merge_review.py` đọc bằng `utf-8` nên có thể gặp cùng vấn đề.
- Đề ẩn có tỉ lệ box gán trùng khác lớp trên cùng vật (11 ảnh) cao hơn hẳn lô luyện tập (2 ảnh) và lô sạch (0). Nhóm coi đây là đặc điểm tự nhiên của COCO và không báo là lỗi; không rõ bộ đáp án đề ẩn có tính các ca này không.
