# AI handoff: Theo dõi video sau đăng

Đọc tài liệu này trước khi sửa Analytics của Content Hub. Các quyết định phạm vi dưới đây
đã được người dùng chốt.

## Quyết định đã chốt

- Một người vận hành quản lý **5 kênh YouTube**: 4 kênh thuộc email 1, 1 kênh thuộc email 2.
- Mỗi kênh có **một lần kết nối Google riêng** và **một token riêng**. Không dùng chung
  `channel==MINE`; mọi truy vấn Analytics dùng `channel==<youtube_channel_id>`.
- Mỗi kênh có reporting job riêng cho CTR/impressions. Token, job ID và snapshot đều gắn
  với kênh; ngắt kết nối một kênh không ảnh hưởng kênh khác.
- `channels.youtube_channel_id` là channel ID dạng `UC…`; `projects.published_at` là ngày
  đăng do người vận hành nhập, dùng làm `startDate` cho Analytics.
- Lưu một snapshot mỗi lần bấm **Làm mới video** hoặc **Làm mới kênh**.
- CTR/impressions lấy từ báo cáo `channel_reach_basic_a1`; báo cáo có thể trễ 1–2 ngày.
  Khi chưa có báo cáo, giao diện để trống và hiển thị cảnh báo.
- Không đăng video hoặc thay đổi nội dung trên YouTube.

Đừng hỏi lại các quyết định trên trừ khi yêu cầu mới mâu thuẫn.

## Luồng dữ liệu và tệp mã

- `app.py`: tab **Theo dõi video sau đăng**. Điểm vào: `_analytics`,
  `refresh_analytics_projects`, `refresh_channel_metrics`, `refresh_selected_analytics`,
  `refresh_channel_analytics`, `connect_google`, `disconnect_google`.
- `youtube_analytics.py`: OAuth Desktop app với PKCE + callback loopback; dùng `urllib`,
  không thêm dependency Google. Lớp chính `YouTubeAnalyticsClient`; token theo kênh tại
  `%LOCALAPPDATA%\YouTubeContentHub\tokens\<channel_id>.json`.
- `store.py`: schema `user_version=6`. Bảng `metrics` giữ snapshot video; bảng
  `channel_metrics` giữ snapshot kênh. `save_analytics_snapshot`,
  `save_channel_analytics_snapshot`, `metric_snapshots`, `channel_metric_snapshots`,
  `delete_analytics_data(actor, channel_id)`.
- `README.md`: hướng dẫn người vận hành và OAuth.
- `build.bat`: đóng gói PyInstaller ra `dist/YouTubeContentHub`; đặt `TCL_LIBRARY`/
  `TK_LIBRARY` từ Python nền để đóng gói Tk đúng. EXE đã chạy self-check UI thành công.

## Ánh xạ chỉ số

| Hiển thị | Nguồn / cách lưu |
|---|---|
| Lượt xem | `views` từ YouTube Analytics API |
| Tổng thời gian xem | `estimatedMinutesWatched`, phút |
| AVD | `averageViewDuration`, giây; UI đổi sang phút:giây |
| Xem trung bình | `averageViewPercentage`, phần trăm |
| Comment / Like | `comments`, `likes` |
| Share | truy vấn `shares` theo `sharingService`, cộng các hàng |
| Impressions / CTR | `channel_reach_basic_a1`, CTR có trọng số impressions trong tối đa 28 ngày |

`metrics.ctr` cũ lưu phần trăm 0–100; `analytics_json.ctr` lưu tỷ lệ 0–1. Snapshot
Analytics không nằm trong `export_bundle`. Nếu video chưa có `published_at`, UI dùng
`created_at` và cần cảnh báo vì đó chưa chắc là ngày đăng thật.

## Cấu hình lần đầu

1. Trong Google Cloud, bật YouTube Analytics API và YouTube Reporting API.
2. Tạo OAuth consent screen và OAuth client loại **Desktop app**.
3. Nếu consent screen ở Testing, thêm cả hai tài khoản Google làm test user.
4. Mở **Quản lý kênh**, nhập `youtube_channel_id` cho từng kênh.
5. Trong tab Analytics, chọn kênh, bấm **Kết nối kênh đang chọn**, chọn file client JSON,
   rồi đăng nhập đúng tài khoản quản lý kênh đó.
6. Nhập link YouTube và ngày đăng ở tab **Thông tin**, sau đó bấm **Làm mới video** hoặc
   **Làm mới kênh**.

Client JSON dùng chung; token/job dùng riêng từng kênh. Không ghi OAuth secret/token vào
chat, database, fixture hay log. **Ngắt kết nối kênh** chỉ thu hồi token và xóa snapshot
của kênh đang chọn.

## Chưa xác nhận bằng chạy thật

- Chưa chạy OAuth/API với credential thật.
- Cần xác nhận: quyền của từng tài khoản với từng kênh, việc tạo job Reporting, thời điểm
  báo cáo CTR xuất hiện, và đơn vị `video_thumbnail_impressions_ctr` trong CSV thật.

## Nguồn API chính thức

- [YouTube Analytics API channel reports](https://developers.google.com/youtube/analytics/channel_reports)
- [YouTube Reporting API channel reports](https://developers.google.com/youtube/reporting/v1/reports/channel_reports)
- [YouTube Reporting API: vòng đời báo cáo](https://developers.google.com/youtube/reporting/v1/reports)
- [YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
