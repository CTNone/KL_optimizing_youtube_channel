---
name: google-flow-video
description: "Nắm bắt, bảo trì và sửa phần tạo video Google Flow từ một ảnh và prompt trong TOOL Video Flow và Desktop NCTT + Thumbnail. Dùng cho chọn Video, setting Veo, upload, nhận clip hoàn tất, tải độ phân giải cao nhất, phục hồi tải và lịch sử video."
---

# Google Flow Video

Skill bàn giao cho AI làm việc với mã nguồn Windows của người dùng. Không phải hướng dẫn API Google Flow hay một tool generate độc lập. Mã và DOM hiện tại là nguồn xác nhận hành vi; giao diện, model và mức tải có thể đổi.

## Bắt đầu nhanh

Đọc [bản đồ dự án](references/project-map.md) để tìm đúng controller đang được shortcut nạp. Khi sửa automation, đọc [luồng và xử lý lỗi](references/workflow-debugging.md). Khi kiểm thử hoặc báo hoàn tất, đọc [kiểm chứng](references/validation.md).

## Hợp đồng sản phẩm

- Video nhận đúng một ảnh địa phương và prompt; lựa chọn model, Thành phần/Khung hình, 16:9/9:16 và x1–x4 phải khớp Desktop.
- Chọn và xác nhận **Video** trong bảng cài đặt trước các setting video. Thumbnail dùng **Hình ảnh**; hai tab dùng chung Chrome/controller, nên chế độ từ lượt trước không chứng minh chế độ lượt này.
- Dùng lại kết nối Chrome/profile và upload ổn định của TOOL THUMBNAIL. Người dùng xử lý đăng nhập/Allow khi Chrome yêu cầu; không coi việc tìm được profile là đã đăng nhập.
- Nhận clip mới hoàn tất rồi mở và tải ngay, không đợi player phát, duration hoặc khoảng ổn định cố định. Chỉ tải kết quả của lượt hiện tại; thumbnail cũ, ảnh đầu vào và thanh tiến độ phát video không phải tiến độ generate.
- Bấm từng clip → xác nhận bản xem → tải mức cao nhất **tài khoản cho phép** → kiểm tra/lưu file → trở về composer. Không mặc định 4K, không tự nâng cấp gói.
- Sau submitAttempted hoặc khi không rõ Flow nhận click, không gửi lại prompt để chữa lỗi tải. Phục hồi bằng lượt và clip đã có; nếu không xác định duy nhất clip thì báo lỗi thay vì đoán.
- Lịch sử và file nằm theo ngày/giờ dưới nơi lưu đã chọn; giữ kết quả tải một phần và lỗi/cảnh báo có thể đọc lại.

## Cách tiếp tục

Xem lỗi đầu tiên, stage và cờ gửi của lượt mới nhất, rồi sửa đúng lớp đang nạp. Tái hiện bằng DOM/fixture trước; nếu cần kiểm tra thật thì dùng phạm vi người dùng đã yêu cầu. Skill không tự cấp quyền tạo thêm nội dung hoặc tiêu thụ tín dụng. Tách rõ kiểm thử cục bộ với kiểm chứng trên tài khoản thật. Sau sửa Python, đóng hoàn toàn Studio và mở lại shortcut để nạp bản mới.
