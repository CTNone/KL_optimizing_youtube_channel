# Kiểm thử và phạm vi bằng chứng

Từ gốc TOOL Video Flow, chạy kiểm thử phù hợp thay đổi:

```powershell
python -m unittest test_video_flow -q
python test_mode_switch.py
python verify_video_settings.py
python verify_video_pipeline.py
```

Đọc entrypoint test trước khi chạy nếu cần biết backend/phụ thuộc. Các test Chrome cục bộ dùng Playwright và Chrome; môi trường sandbox có thể cần quyền khởi chạy subprocess. `verify_thumbnail_pipeline.py` phù hợp khi sửa inject/mode dùng chung với Thumbnail.

- Unit tests: stage/cờ gửi, không submit trùng, tải một phần, retry, hủy, nhận ngay kết quả mới, loại clip cũ.
- Settings/mode: sidebar trùng tên; menu đã mở, dựng lại/đóng; ARIA/màu; model có mô tả; menu Angular thật đã ghi; disabled 4K; thumbnail-only 99%→100%.
- Pipeline localhost: dùng FlowErrors thật trong runtime nhưng media/Flow là giả lập; gửi một lần, nhiều clip lazy-load, native download, cache và hủy. Không gọi đây là kiểm chứng tài khoản Google.

Một số fixture đọc `live-resolution-diagnostic.json`, `REAL_FLOW_TEST.json` và MP4 của lượt thật. Nếu chuyển máy thiếu artifact, dùng fixture cục bộ tương đương hoặc báo rõ test chưa chạy; không gọi real_flow_check.py chỉ để tạo lại dữ liệu test.

## Bằng chứng trên tài khoản thật

Ngày 07/10/2026 đã upload một ảnh, prompt “tuyết rơi.”, Veo 3.1 - Lite, Thành phần, 16:9, x1. Tải qua UI Flow ở 1080p, 4K bị khóa; MP4 thực tế 1920×1080, 8 giây, 23.310.045 byte. Tải lại cùng clip, không submit thêm; đã xác nhận trở về composer.

Bằng chứng trong dự án: `REAL_FLOW_RESULT.json`, `REAL_FLOW_TEST.json`, lượt `Documents/TOOL Video Flow OUTPUT/Video/2026-10-07/13-00-20_ce8ac028/video.json`, sidecar/hash MP4 và `AUDIT.md`. Đây là dữ kiện cũ của tài khoản lúc kiểm tra; không chứng minh mức tải hoặc model còn giống hôm nay.

Những sửa sau đó về nhận thumbnail-only/kiểm tra 0,25 giây và mode/remount được kiểm thử cục bộ. Chưa chứng minh toàn bộ các thay đổi sau đó trên Google thật; 9:16/x2–x4/tài khoản khác cũng chưa có bằng chứng thật. Header/hash và MP4 track metadata không chứng minh giải mã đầy đủ mọi frame.

## Khi cần kiểm tra thật

Tạo nội dung thật chỉ trong yêu cầu được người dùng cho phép, với ảnh/prompt/model rõ ràng. Ưu tiên clip đã tạo nếu sửa tải. `real_flow_check.py` là script chẩn đoán có khả năng generate khi marker chưa có; đọc script và marker trước chạy, không coi là smoke test vô hại. Khi đã submit/không rõ kết quả, dừng generate và phục hồi đúng lượt. Hết timeout hoặc selector không duy nhất: lưu lỗi/bằng chứng, không gửi tiếp để thử may rủi.

Báo điều đã làm, file tải và geometry thực nếu có, điều chỉ test localhost, và giới hạn còn lại. Khi sửa mã, nhắc đóng hoàn toàn Studio rồi mở lại shortcut vì process cũ giữ class Python đã nạp.
