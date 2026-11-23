# AI handoff: Theo dõi video sau đăng

Đọc tài liệu này trước khi tiếp tục sửa tính năng Analytics của Content Hub. Đây là
ghi chú kỹ thuật cho phiên làm việc sau; các quyết định phạm vi đã được người dùng chốt.

## Quyết định đã chốt

- Thêm tab cấp ứng dụng **Theo dõi video sau đăng** cho các dự án có trạng thái `published`.
- Nguồn dữ liệu là Google OAuth chỉ đọc, YouTube Analytics API và YouTube Reporting API.
- Lưu một snapshot mới mỗi lần người dùng bấm **Làm mới chỉ số**.
- Chỉ số giữ chân hiển thị dưới dạng tỷ lệ xem trung bình; không cần biểu đồ theo từng đoạn.
- CTR thumbnail lấy từ báo cáo Reporting API mới nhất hiện có. Báo cáo này chạy theo ngày,
  nên CTR có thể trễ khoảng 1–2 ngày. Khi chưa có báo cáo, giao diện để trống và báo trạng thái.
- Không đăng video hoặc thay đổi nội dung trên YouTube.

Đừng hỏi lại các quyết định trên trừ khi có mâu thuẫn mới trong yêu cầu tiếp theo.

## Luồng dữ liệu và tệp mã

- `app.py`: tạo tab chính, liệt kê video đã đăng, chọn dự án, chạy thao tác API nền,
  hiển thị lịch sử snapshot và nút kết nối/ngắt kết nối. Điểm vào: `_analytics`,
  `refresh_analytics_projects`, `refresh_selected_analytics`, `connect_google`,
  `disconnect_google`.
- `youtube_analytics.py`: OAuth Desktop app với PKCE và callback loopback cục bộ;
  gọi API bằng thư viện chuẩn Python (`urllib`), không thêm dependency Google.
  Lớp chính: `YouTubeAnalyticsClient`.
- `store.py`: schema 5; thêm các cột chỉ số nullable và `analytics_json` theo migration
  cộng thêm, giữ được database cũ. `save_analytics_snapshot` ghi nguồn
  `youtube_analytics`; `metric_snapshots` đọc lịch sử.
- `README.md`: hướng dẫn người vận hành và cài OAuth.
- `KIEN_TRUC_VA_PHAM_VI.md`, `KE_HOACH_KHOA_LUAN.md` và `../docs/DAC_TA_HE_THONG.md`:
  tài liệu phạm vi/kiến trúc khóa luận đã cập nhật.

`OPEN_CONTENT_HUB.bat` chạy source bằng `py app.py`. EXE có sẵn trong `dist/` được đóng
gói trước tính năng này; cần build lại nếu muốn dùng EXE có tab Analytics.

## Ánh xạ và cách hiểu chỉ số

| Hiển thị | Nguồn / cách lưu |
|---|---|
| Lượt xem | `views` từ YouTube Analytics API |
| Tổng thời gian xem | `estimatedMinutesWatched`, đơn vị phút |
| AVD | `averageViewDuration`, giây; giao diện đổi sang phút:giây |
| Xem trung bình | `averageViewPercentage`, phần trăm |
| Comment / Like | `comments`, `likes` |
| Share | truy vấn `shares` theo dimension bắt buộc `sharingService`, cộng các hàng trả về |
| Impressions / CTR | Báo cáo `channel_reach_basic_a1`, tính CTR có trọng số impressions trên tối đa 28 ngày báo cáo hiện có |

API Analytics truy vấn tổng hợp từ ngày `created_at` của dự án Hub tới ngày hiện tại;
đây chưa chắc là ngày đăng YouTube. Nếu cần chính xác từ ngày xuất bản, bổ sung trường
`published_at` bền vững rồi dùng trường đó làm `startDate`.

Trong `metrics`, cột tương thích cũ `ctr` lưu phần trăm 0–100; `analytics_json.ctr` lưu
tỷ lệ 0–1. Các chỉ số còn lại từ API lưu trong cột mở rộng/JSON. Snapshot Analytics
được giữ trong database Hub, nhưng cố ý không đưa vào `export_bundle`.

## Cấu hình lần đầu

1. Trong Google Cloud, bật YouTube Analytics API và YouTube Reporting API.
2. Cấu hình OAuth consent screen và tạo OAuth client loại Desktop app.
3. Nếu consent screen ở Testing, thêm tài khoản Google làm test user.
4. Trong tab, chọn **Kết nối Google…**, chọn file client JSON, rồi đăng nhập tài khoản
   có quyền Analytics của kênh.
5. Chọn một video đã đăng, có URL YouTube lưu ở tab **Kiểm duyệt và Đăng**, rồi bấm
   **Làm mới chỉ số**.

Client JSON, token và reporting job ID nằm ngoài repository tại
`%LOCALAPPDATA%\YouTubeContentHub`. Không yêu cầu hoặc ghi OAuth secret/token vào chat,
database, test fixture hay log. **Ngắt kết nối & xóa snapshot** thu hồi token và xóa
snapshot Analytics đã lưu trong database hiện tại.

## Chưa được xác nhận bằng chạy thật

OAuth/API chưa được thực hiện bằng credential của người dùng. Do đó cần kiểm tra lần
đầu với cấu hình thật: consent screen, quyền tài khoản/kênh, tạo reporting job, thời
điểm báo cáo CTR xuất hiện, và định dạng CSV/giá trị CTR được tài khoản trả về.
Đặc biệt, xác nhận đơn vị `video_thumbnail_impressions_ctr` với dữ liệu thật trước khi
đổi phép chuẩn hóa CTR.

Trong phiên trước, không chạy test hoặc build EXE. Nếu người dùng yêu cầu kiểm thử,
theo hướng dẫn repository chạy unittest từ `CONTENT HUB/`; kiểm thử API thật chỉ sau khi
có cấu hình và người dùng yêu cầu rõ.

## Nguồn API chính thức

- [YouTube Analytics API channel reports](https://developers.google.com/youtube/analytics/channel_reports)
- [YouTube Reporting API channel reports](https://developers.google.com/youtube/reporting/v1/reports/channel_reports)
- [YouTube Reporting API: vòng đời báo cáo](https://developers.google.com/youtube/reporting/v1/reports)
- [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
