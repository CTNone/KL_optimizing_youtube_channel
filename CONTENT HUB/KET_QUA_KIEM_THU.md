# Kết quả kiểm thử bản MVP

Ngày: 16/10/2026. Môi trường: Windows, Python 3.13, SQLite, Tk 8.6 và FFmpeg có sẵn
trong editor. Không gửi yêu cầu tạo ảnh/video hoặc gọi API YouTube trong đợt này.

## Đã đạt

- **14 kiểm thử tự động**: tách dữ liệu kênh, lưu trữ kênh, gate workflow, optimistic
  revision, asset version/dedup, QC đầy đủ, file bị đổi ngoài hệ thống, yêu cầu sửa,
  lịch đăng/URL, metric validation, job uniqueness/recovery/cancel, backup nhất quán,
  process lock và render tích hợp thực.
- Render tích hợp dùng clip tổng hợp 24 fps, chuẩn hóa 30 fps, xuất 720p và đăng ký
  đúng asset/job/provenance trong SQLite.
- Khởi tạo UI source và EXE: 6 tab, đọc được hai kênh/hai dự án demo, tìm đủ các
  adapter. Cửa sổ tự đặt 1400×774 trên màn hình 1536×864.
- **Chính bản EXE** tạo clip tổng hợp và render thành công 6.0 giây, H.264,
  1280×720, 180 khung hình, không tiếng theo chủ đích. Engine/FFmpeg lấy từ gói EXE.
- Database sản xuất không được seed dữ liệu demo; release smoke dùng database riêng.

Các báo cáo máy đọc nằm tại `data/ui_selfcheck.json`, `data/packaged_ui_check.json`
và `data/packaged_render_check.json`; media của release smoke nằm dưới
`data/release_checks/`.

## Chưa có bằng chứng đầy đủ

- Chụp hình kiểm tra giao diện qua computer-use bị lỗi `FrameArrived timed out` và
  `window capture timed out` sau lần phục hồi. Vì vậy chưa xác nhận bố cục bằng ảnh
  hoặc toàn bộ thao tác click xuyên suốt; không đồng nhất UI self-check với visual QA.
- Chưa đo so sánh thời gian vận hành thủ công và Hub trên tập dự án thực.
- Chưa kiểm chứng một chu kỳ sản xuất mới trên tài khoản Google Flow/YouTube thật.
  Bộ điều khiển Flow hiện có được mở qua launcher, không bị sửa trong đợt này.
- Hub render bằng CPU; chưa kiểm tra các cấu hình GPU từ Hub.

## Chạy lại

```
py -m unittest test_hub -v
py app.py --demo --self-check data/ui_selfcheck.json
dist/YouTubeContentHub/YouTubeContentHub.exe --demo --self-check data/packaged_ui_check.json
dist/YouTubeContentHub/YouTubeContentHub.exe --smoke-render data/packaged_render_check.json
```

Lệnh smoke tạo một thư mục/database mới cho mỗi lần chạy, không sửa database sản xuất.
Không cần lặp lại smoke khi chỉ sửa nội dung tài liệu.
