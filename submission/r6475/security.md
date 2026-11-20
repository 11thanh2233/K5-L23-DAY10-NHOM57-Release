# Bảo mật khi làm việc

> Gắn với lô nhóm vừa bàn giao: v1 `lab250_9b6266dd5aa0` (250 ảnh, đang HOLD) và v2 `lab250_9b6266dd5aa0_v2` (240 ảnh, 1598 nhãn, 10 ảnh trong `rework_queue.csv`).

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp

Không chép lô ra USB. Lô này có 250 ảnh và file `jobs.csv` ghi mã người gán, người kiểm (A01–A05, Q01–Q03); USB rơi hoặc cắm vào máy nhà nhiễm mã độc là lộ cả dữ liệu lẫn thông tin nhân sự, và không ai truy được bản sao đó đã đi đâu. Gửi lô qua email cá nhân cũng sai vì dữ liệu ra khỏi hệ thống công ty và nằm lại trên server bên thứ ba; nhờ người khác làm hộ thì người đó không có quyền với job này và mọi nhãn họ gán sẽ ghi sai người trong truy vết. Cách đúng: dừng ở mốc an toàn, ghi lại trạng thái (ví dụ còn bao nhiêu ảnh trong hàng đợi review), báo trưởng nhóm xin gia hạn hoặc chia lại việc, hôm sau làm tiếp trên máy công ty hoặc qua VPN/remote desktop mà công ty cấp.

## 2. Năm việc: được hay không

- **Mở job được giao trên máy công ty: được.** Đúng người, đúng máy, đúng quyền; mọi thao tác có log để truy vết như cột `annotator`/`reviewer` trong `truyvet.csv`.
- **Chụp màn hình gửi người quen: không.** Ảnh chụp mang theo nội dung lô ra ngoài, không thu hồi được; trong lô có ảnh người thật nhìn rõ mặt (mục 3).
- **Chép lô ra USB: không.** Như mục 1: mất kiểm soát bản sao, không truy được, dễ thất lạc.
- **Dán nhãn thật lên chatbot: không.** Dữ liệu dán vào chatbot công cộng có thể bị lưu và dùng lại ngoài hợp đồng. Lab này dùng ảnh COCO công khai nên nhóm được hỏi AI và đã ghi vào `prompts.md`; với dữ liệu thật của dự án thì không được làm vậy.
- **Đưa tài khoản CVAT cho đồng nghiệp: không.** Mọi nhãn sẽ ghi dưới tên mình; khi team AI báo lỗi như ticket truck, truy vết sẽ chỉ sai người và `rework_queue.csv` giao việc sai người. Mỗi người dùng tài khoản riêng, xin quyền qua trưởng nhóm.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ

Lô có ảnh mặt người nhìn rõ, đều nằm trong lô v2 vừa đóng gói: `000000004134` (hai người đàn ông bắt tay trong hội trường, mặt nhìn thẳng, rõ nét), `000000006894` (người đàn ông đeo kính cười cạnh con voi, mặt chiếm phần lớn khung hình), `000000019402` (hai người trùm mũ áo khoác chụp cận mặt). Khi thấy ca như vậy: đặt trạng thái lô là **Hold**, không giao v2 cho team AI, ghi danh sách ảnh có mặt người và **báo người phụ trách** dữ liệu (trưởng nhóm, người quản lý dự án hoặc bộ phận pháp chế/bảo mật). Không tự làm mờ vì sửa ảnh sẽ đổi sha256 trong `manifest.csv`, phá tính truy vết, và người gán không có thẩm quyền quyết định cách ẩn danh (mức làm mờ, có cần xin đồng ý hay loại ảnh); không tự xoá ảnh vì mất bằng chứng và làm lệch số liệu QC (`README.txt` ghi 240 ảnh). Người phụ trách quyết định cách xử lý, sau đó tạo lô mới có lô cha ghi trong lineage, giống cách v2 kế thừa v1.
