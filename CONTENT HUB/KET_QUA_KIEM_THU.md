# Kết quả kiểm thử bản MVP

Ngày: 16/10/2026. Môi trường: Windows, Python 3.13, SQLite, Tk 8.6 và FFmpeg có sẵn
trong editor. Không gửi yêu cầu tạo ảnh/video hoặc gọi API YouTube trong đợt này.

> **Trạng thái bằng chứng:** đây là báo cáo snapshot của bản được kiểm tra ngày
> 16/10/2026, không phải xác nhận cho toàn bộ working tree hiện tại. Các thay đổi sau
> ngày này và bản phát hành dùng để bảo vệ cần được kiểm tra lại theo checklist ở
> `KE_HOACH_KHOA_LUAN.md`. Không dùng kết quả dưới đây để khẳng định bản hiện tại đã qua
> nghiệm thu.

## Đã đạt

- **14 kiểm thử tự động**: tách dữ liệu kênh, lưu trữ kênh, gate workflow, optimistic
  revision, asset version/dedup, QC đầy đủ, file bị đổi ngoài hệ thống, yêu cầu sửa,
  lịch đăng/URL, metric validation, job uniqueness/recovery/cancel, backup nhất quán,
  process lock và render tích hợp thực.
- Render tích hợp dùng clip tổng hợp 24 fps, chuẩn hóa 30 fps, xuất 720p và đăng ký
  đúng asset/job/provenance trong SQLite.
- Khởi tạo UI source và EXE: 6 tab, tại thời điểm báo cáo đọc được hai kênh/hai dự án demo, tìm đủ các
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

## Kiểm chứng bổ sung ngày 04/11/2026

- Chạy `py -m unittest test_hub -v`: **15/15 ca đạt** trên working tree hiện tại; gồm
  kiểm tra seed demo đa kênh/lặp an toàn và render tích hợp bằng clip tổng hợp.
- Self-check UI source trên database tạm sạch: **6 tab, 3 kênh, 6 album, 12 video/mix**;
  mở được dự án demo. Database demo có sẵn không bị sửa.
- Build QA bằng PyInstaller 6.22.3 vào `dist/archive/qa_20261104_tk`; Tcl/Tk được thu thập đầy
  đủ sau khi chỉ định `TCL_LIBRARY`/`TK_LIBRARY`. Các bản build lịch sử hiện được lưu
  trong `dist/archive/`.
- Packaged UI self-check: `ui: OK`, **6 tab, 3 kênh, 12 video/mix**, cửa sổ 1400×774
  trên màn hình 1536×864. Chạy trong workspace giả lập cô lập nên adapter ngoài được báo
  không khả dụng; self-check này chỉ chứng minh Tk/UI và dữ liệu demo đóng gói.
- Packaged smoke render thành công: 6 giây, H.264, 1280×720, 180 khung hình; kiểm tra
  duration/resolution/audio/frames đều đạt. Báo cáo: `data/packaged_render_qa_20261104.json`.
- `git diff --check` trên các tài liệu và mã đã sửa không báo lỗi whitespace.
- Hai lần chạy trong sandbox không vào được bước tạo SQLite ở thư mục tạm. Sau khi chạy
  cùng bộ lệnh với quyền ghi tạm phù hợp, toàn bộ 15 ca hoàn tất thành công.
- Không gọi Google Flow, YouTube API hoặc tạo nội dung trên tài khoản thật.
- Chưa có visual QA bằng ảnh/chụp thao tác. Bản EXE QA đã build/self-check, nhưng chưa
  phát hành thay thế EXE hiện có; cần kiểm tra adapter trong workspace thật. Database demo
  hiện có là dữ liệu cũ (2 kênh, 0 album, 2 dự án); không sửa database này. Ca seed mới
  dùng database tạm sạch, cho kết quả 3 kênh, 6 album và 12 video/mix.

## Chạy lại

```
py -m unittest test_hub -v
py app.py --demo --self-check data/ui_selfcheck.json
dist/archive/YouTubeContentHub/YouTubeContentHub.exe --demo --self-check data/packaged_ui_check.json
dist/archive/YouTubeContentHub/YouTubeContentHub.exe --smoke-render data/packaged_render_check.json
```

Lệnh smoke tạo một thư mục/database mới cho mỗi lần chạy, không sửa database sản xuất.
Không cần lặp lại smoke khi chỉ sửa nội dung tài liệu.
