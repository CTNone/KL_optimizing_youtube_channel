# Kết quả kiểm thử bản MVP

Ngày: 23/11/2026. Môi trường: Windows, Python 3.13, SQLite và Tk 8.6. Không gửi yêu cầu
tạo ảnh/video, không gọi Google Flow và không gọi YouTube API trong đợt này.

> **Trạng thái bằng chứng:** đây là báo cáo cho working tree ngày 23/11/2026. Analytics
> mới được kiểm thử ở tầng dữ liệu/UI, chưa chạy OAuth hoặc API bằng credential thật.

## Đã đạt

- Chạy `py -m unittest test_hub -v`: **18/18 ca đạt**.
- Phạm vi kiểm thử: tách dữ liệu kênh; lưu trữ kênh; gate workflow; đổi Bước tay có audit;
  optimistic revision; asset version/dedup; QC đầy đủ; file bị đổi ngoài hệ thống; yêu cầu
  sửa; lịch đăng/URL; `published_at`; metric validation; backup nhất quán; process lock;
  YouTube channel ID duy nhất/hợp lệ; snapshot kênh và xóa Analytics theo kênh; snapshot
  project trước khi xóa; seed demo đa kênh/lặp an toàn; tính CTR có trọng số impressions.
- Self-check UI source trên database sản xuất: **UI OK, 5 tab, 3 kênh, 0 project**; adapter
  NCTT và Music Manager tìm thấy. Cửa sổ 1400×774 trên màn hình 1536×864.
- Self-check UI demo trên database mới: **UI OK, 5 tab, 3 kênh, 12 video/mix**.
- Đã build EXE `dist/YouTubeContentHub/YouTubeContentHub.exe` và self-check UI qua EXE:
  5 tab, 3 kênh, 0 project; `build.bat` đặt `TCL_LIBRARY`/`TK_LIBRARY` để đóng gói Tk đúng.
- Database demo mới có 3 kênh, 6 album và 12 video/mix; seed chạy hai lần vẫn không nhân
  đôi dữ liệu.
- Bỏ render/Tool Edit/FFmpeg khỏi Hub; `services.py`, `build.bat` và `.spec` không còn
  tham chiếu engine/FFmpeg. `smoke.py` đã xóa.
- Bỏ playlist nhạc riêng từng video khỏi Hub; dữ liệu `music_*` và Music Manager được giữ.
- Dữ liệu test production đã được xóa và backup trước khi xóa:
  `OUTPUT TỔNG/Content Hub/Backups/content_hub_before_cleanup_20261123_185206.sqlite3`.
  Backup demo cũ: `demo_before_cleanup_20261123_185206.sqlite3` trong cùng thư mục.

Báo cáo máy đọc: `OUTPUT TỔNG/Content Hub/selfcheck.json`,
`OUTPUT TỔNG/Content Hub/demo_selfcheck.json`, `OUTPUT TỔNG/Content Hub/exe_selfcheck.json`
và `OUTPUT TỔNG/Content Hub/exe_demo_selfcheck.json`.

## Chưa có bằng chứng đầy đủ

- Chưa chạy OAuth/YouTube Analytics/Reporting với credential thật; chưa xác nhận quyền
  của 5 kênh, việc tạo reporting job, độ trễ báo cáo và đơn vị CTR trong CSV thật.
- Chưa đo so sánh thời gian vận hành thủ công và Hub trên tập dự án thực.
- Chưa chụp hình/visual QA toàn bộ thao tác click xuyên suốt.
- Chưa đăng video thật hoặc kiểm chứng liên kết giữa Hub và YouTube Studio.

## Chạy lại

```
py -m unittest test_hub -v
py app.py --self-check "..\OUTPUT TỔNG\Content Hub\selfcheck.json"
py app.py --demo --self-check "..\OUTPUT TỔNG\Content Hub\demo_selfcheck.json"
build.bat
dist\YouTubeContentHub\YouTubeContentHub.exe --self-check "..\OUTPUT TỔNG\Content Hub\exe_selfcheck.json"
```

Lệnh self-check chỉ đọc/khởi tạo UI và ghi báo cáo; database demo được seed idempotent.
Không chạy lệnh Analytics thật nếu chưa có OAuth client và chưa được người dùng cho phép.
