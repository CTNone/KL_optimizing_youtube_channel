---
name: google-flow-thumbnail
description: "Nắm bắt, bảo trì và sửa luồng tạo thumbnail Google Flow của dự án TOOL THUMBNAIL và phần mềm Desktop NCTT + Thumbnail. Dùng khi xử lý chọn mô hình, tỉ lệ, ảnh mẫu, prompt, tải 2K hoặc crop 16:9 trong dự án này."
---

# Google Flow Thumbnail

Skill bàn giao cho AI tiếp tục phát triển phần Thumbnail của dự án Windows hiện có. Đây là hướng dẫn cho mã nguồn của người dùng, không phải tài liệu API Google Flow. Các tên mô hình và giao diện Flow có thể thay đổi; kiểm tra mã hiện tại, log và giao diện trước khi kết luận.

## Đọc nhanh

- Đọc [kiến trúc và vị trí mã](references/project-map.md) khi bắt đầu để xác định đúng chương trình đang chạy. Desktop tích hợp có lớp ghi đè riêng; sửa extension đơn thuần có thể không sửa được Desktop.
- Đọc [trình tự và xử lý lỗi](references/workflow-debugging.md) khi sửa automation. Tập trung vào bước đầu tiên bị lỗi trong lượt mới nhất.
- Đọc [kiểm thử và tình trạng bàn giao](references/validation.md) trước khi kiểm tra hoặc báo hoàn tất.

## Yêu cầu đã thống nhất của sản phẩm

- Người dùng tự mở và đăng nhập hồ sơ Chrome, tự đổi tài khoản khi hết lượt. Desktop điều khiển tab Flow đã mở; không tự thay tài khoản.
- Mô hình, tỉ lệ và số ảnh trên Flow phải khớp lựa chọn Desktop. Không dùng mô hình khác chỉ vì đang có sẵn trên Flow.
- Có thể gửi prompt riêng hoặc ảnh mẫu địa phương kèm prompt, gồm thumbnail lấy từ TOOL NCTT.
- Tải 2K miễn phí khi Flow cung cấp; kiểm tra file thực tế, không lưu thumbnail xem trước thay cho ảnh 2K.
- Lưu bản gốc và bản crop 16:9. Nguồn 4:3 có thể cắt 25% chiều cao phía dưới; với tỉ lệ khác phải dùng công thức crop 16:9 hiện có.
- Hiển thị đường dẫn đầy đủ trên Windows và lỗi có thể mở lại trong lịch sử; không làm mất lỗi sau vài giây.
- Chỉ đánh dấu hạn mức theo từng mô hình sau ít nhất ba sự kiện lỗi hạn mức riêng biệt. Lỗi UI, upload hoặc lưu file không chứng minh mô hình hết lượt.
- Thao tác đủ chậm để người dùng quan sát. Luồng Desktop đang dùng F5, đợi sự kiện load rồi thêm 2 giây trước bước tiếp theo.

## Những điều quyết định độ tin cậy

1. Xác nhận chế độ Hình ảnh, rồi mô hình, tỉ lệ, số ảnh trước khi upload/gửi. Trạng thái nút sáng hoặc có focus không chứng minh đã chọn.
2. Bảng cài đặt và danh sách mô hình là hai lớp. Nút tóm tắt cạnh prompt vẫn có thể hiện dưới menu; đừng bấm nó khi đang chờ danh sách con.
3. Đợi upload kết thúc và nhận diện đúng ảnh mới của lượt upload hiện tại trước khi thêm vào prompt. Không chọn ảnh đầu tiên trong thư viện hoặc dựa vào vị trí `nth()` cũ.
4. Xác nhận Flow nhận lệnh gửi rồi mới theo dõi kết quả mới. Không tải ảnh mẫu hoặc ảnh cũ như kết quả.
5. Sau khi đã gửi hoặc không rõ lần bấm gửi có thành công, không gửi lại để chữa lỗi tải/lưu. Tách retry lưu file khỏi generate.
6. Sau tải, trở về composer để phục vụ lượt tiếp theo; nếu không xác nhận được giao diện, ghi rõ cảnh báo trong log.

## Cách tiếp tục một yêu cầu sửa lỗi

Xác định shortcut/lớp controller thực tế, lấy lỗi và thời gian của lượt mới nhất, đọc hàm liên quan rồi tạo kiểm thử tái hiện hành vi. Thay đổi đúng lớp đang được nạp, kiểm tra bằng HTML giả lập/kiểm thử hiện có trước khi áp dụng. Khi cần kiểm tra trên Flow thật, chỉ thực hiện tác vụ tạo ảnh trong phạm vi người dùng đã yêu cầu; skill này không tự cấp quyền tiêu thụ lượt tạo ảnh.

Báo riêng kết quả kiểm thử giả lập và kết quả trên Flow thật. Không gọi một bản sửa đã được xác minh trên tài khoản nếu chỉ chạy Chrome headless với HTML cục bộ. Sau thay đổi Python, người dùng cần đóng hoàn toàn Desktop rồi mở lại shortcut để nạp bản mới.
