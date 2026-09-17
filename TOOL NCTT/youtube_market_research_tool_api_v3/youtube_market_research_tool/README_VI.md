# YouTube Music Market Research — API V3

Công cụ Windows/Tkinter dùng **YouTube Data API v3**, không scraping HTML.

## V3 có gì mới?

- Bộ đếm quota theo ngày, lưu cục bộ trong `quota_usage.json`.
- Hiển thị quota ngay trên giao diện và trong log.
- Tự động dừng trước ngưỡng dự phòng để tránh tiếp tục gọi API.
- Mặc định giả lập giới hạn an toàn:
  - Search API: 100 calls/ngày.
  - API khác: 10.000 units/ngày.
- Có thể chỉnh mức **Dự phòng Search quota** và **Dự phòng API khác**.
- Tìm kiếm theo từng trang và lấy chi tiết từng batch ngay sau mỗi trang; nếu đã đủ số video tối đa thì tự dừng, không gọi thêm Search.
- Không có tính năng tự động nghe/xem/like/comment.

## Lưu ý quan trọng về quota

`quota_usage.json` chỉ ghi nhận các request mà **chính tool này** đã thực hiện bằng API key đó trên máy này. Nó không biết quota đã bị dùng bởi YouTube Studio, ứng dụng khác, máy khác hoặc project khác.

Vì vậy bộ đếm là **bộ đếm an toàn nội bộ**, không phải số quota realtime do Google trả về.

## Cài đặt

1. Cài Python 3.10+.
2. Chạy `run.bat`.
3. Nhập API key YouTube Data API v3 vào ô API Key.
4. Bấm **Lưu API key**.
5. Bấm **Xem quota** để xem bộ đếm cục bộ.
6. Thiết lập Keyword, năm, view tối thiểu và khoảng video.
7. Bấm **BẮT ĐẦU NGHIÊN CỨU**.

## Các file quan trọng

- `app.py`: chương trình chính.
- `api_key.txt`: API key được lưu cục bộ.
- `quota_usage.json`: bộ đếm quota theo ngày và theo API key.
- `exports/`: Excel/CSV.
- `thumbnails/`: thumbnail nếu bật tùy chọn tải thumbnail.
