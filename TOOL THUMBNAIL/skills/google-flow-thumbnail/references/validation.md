# Kiểm thử và tình trạng bàn giao

## Môi trường

Windows PowerShell; đã dùng Python 3.13, Playwright, Pillow, Node.js trên máy. Kiểm tra lại dependency hiện tại trước chạy. Không cần cài thêm thư viện chỉ để đọc skill.

Các kiểm thử browser dưới đây dùng Chrome headless với HTML cục bộ, không gửi prompt tới Flow thật. Các bản sửa trong phiên trước đã qua kiểm thử này, nhưng người dùng vẫn phát hiện khác biệt UI thật; không coi fixture là bằng chứng selector phù hợp mọi phiên bản Flow.

## Kiểm thử theo phạm vi

Chạy từ `TOOL THUMBNAIL` khi sửa JS chung:

```powershell
node chrome-extension/test-clicks.cjs
node chrome-extension/test-downloads.cjs
node chrome-extension/test-pipeline.cjs
node chrome-extension/test-download-capture.cjs
node chrome-extension/test-native-click.cjs
```

- `test-clicks`: overlay trong thẻ nhiều lớp, target ngoài thẻ, toolbar, target disabled/detached.
- `test-downloads`: ảnh đúng/sai, phần tử ảnh bị thay, preview nhỏ hơn lưới, 2K/1K/có phí, retry ghi không tải trùng, cleanup.
- `test-pipeline`: chọn model, count, gửi, reference và lưu kết quả qua bridge giả lập.
- `test-download-capture`: chỉ bắt lượt download đã arm đúng nguồn/dự án.

Chạy từ `TOOL Video Flow` khi sửa Desktop tích hợp:

```powershell
python -m unittest test_video_flow -v
python -m unittest test_mode_switch -v
```

`test_video_flow` có kiểm tra Thumbnail xác nhận model trước resume và dừng trước gửi nếu thất bại, cùng logic vòng đời Video. `test_mode_switch` kiểm tra sidebar trùng label, bảng remount, menu tự đóng và Omni x2 → Veo Lite x1. Chỉ chạy các nhóm liên quan thay đổi.

Tại TOOL THUMBNAIL có `test_thumbnail_model_pointer.py`: fixture chọn model bằng pointer rồi ratio/count; nó import mã trong `mode-review`. Nếu dùng để xác minh bản đang cài, đối chiếu với file thật trong TOOL Video Flow hoặc điều chỉnh đường dẫn trước, tránh chỉ kiểm tra bản review cũ.

`test_desktop_flow.py`, `test_integration.py`, `test_chrome_profile.py`, `chrome-extension/native-host/test_host.py` phục vụ uploader, tích hợp, profile, file/crop; chọn test theo hàm sửa thay vì chạy mọi thứ mặc định.

## Áp dụng bản sửa

Kiểm tra source đang được nạp trước khi sửa. Nếu cần chỉnh sibling TOOL Video Flow ngoài workspace writable, dùng cơ chế quyền filesystem của môi trường; không giả định skill cấp quyền. Đối chiếu bản review và bản triển khai nếu dùng staging. Đóng hoàn toàn app Python để nạp mã mới; mở shortcut khi instance cũ còn chạy có thể chỉ báo app đã mở.

## Tình trạng đã biết khi bàn giao

- Người dùng đã xác nhận Desktop chọn Hình ảnh và model đúng sau bản sửa dùng Playwright.
- Sau đó người dùng báo chưa tới upload/prompt; state mới nhất lúc chẩn đoán ghi `settings_failed`: không thấy lựa chọn tỉ lệ. Đã sửa giữ bảng sẵn sàng cho ratio/count và qua kiểm thử; chưa có xác nhận end-to-end mới từ người dùng.
- Có lượt đã tạo ảnh nhưng tải thất bại vì xác nhận preview; đã sửa identity/remount/overlay và preview nhỏ hơn lưới, qua test cục bộ. Chưa có xác nhận tải hoàn tất trên tài khoản sau bản sửa cuối.
- Lỗi Video mới nhất trong hội thoại do Flow đang chọn Omni 1.1 Flash thay vì Veo. Đã sửa trigger, test Omni x2 → Veo Lite x1, áp dụng vào app; chưa có phản hồi chạy thật sau sửa.
- Lần thử đọc DOM tab Flow qua CDP trong phiên trước bị timeout; không có DOM snapshot thực tế để bảo đảm mọi selector.

Khi nhận task mới, đọc lịch sử mới hơn các thông tin trên. Không làm mất kết quả đã tạo, không generate lại chỉ vì thiếu file tải. Báo rõ bước nào đã xác minh bằng test và bước nào cần quan sát trên Flow hiện tại.
