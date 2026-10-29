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
- `TOOL Video Flow OUTPUT/NCTT/<keyword>_<thời gian>_<mã riêng>/`: thư mục riêng cho mỗi lần chạy, chứa Excel/CSV và thư mục `thumbnails/`. Các kết quả cũ được giữ nguyên.
- Thumbnail mặc định được nhúng vào cột `Thumbnail` của sheet `VIDEOS`; ảnh vẫn hiển thị khi chuyển file Excel sang máy khác. Có thể bỏ chọn trên giao diện; CSV giữ URL ảnh. Nếu tải ảnh lỗi, báo cáo ghi rõ ảnh không khả dụng.


## Trang Search tối đa / năm

Đây là giới hạn độ rộng tìm kiếm, không phải chỉ số đánh giá chất lượng video. Mỗi trang gọi Search một lần và trả tối đa 50 ứng viên trước bộ lọc. Ví dụ 10 trang × 2 năm: tối đa 20 lượt Search và 1.000 ứng viên (có thể ít hơn hoặc trùng nhau), chưa tính các lượt lấy chi tiết video/kênh.

Tăng số trang có thể giúp tìm thêm video khi bộ lọc chặt, nhưng tốn thêm quota và thời gian; không bảo đảm đủ video tối thiểu. Tool dừng sớm nếu đủ video tối đa, hết trang kết quả hoặc chạm ngưỡng dự phòng. Hiện tool xét năm mới trước, nên có thể dừng trước khi xét năm cũ; kết quả không phải bảng xếp hạng toàn bộ thị trường qua mọi năm.


## Bộ lọc Shorts

- `Bao gồm video Shorts (lọc theo thời lượng)` mặc định bỏ chọn: chỉ giữ video dài hơn 180 giây, loại cả video không rõ thời lượng.
- Khi bật: nhận video ở mọi thời lượng, vẫn áp dụng các bộ lọc khác.
- YouTube Data API công khai không cung cấp cờ Shorts. Bộ lọc dùng thời lượng để tránh Shorts, nên cũng loại video thường dài ≤ 3 phút. Không dùng `videoDuration=short` để nhận diện Shorts: tham số API này có nghĩa là video dưới 4 phút.
- Bộ lọc được áp dụng trước khi đếm số video đạt yêu cầu và trước khi quyết định dừng tìm kiếm. Nhật ký ghi chế độ và số ứng viên bị loại; sheet `SUMMARY` ghi chế độ lọc nếu có kết quả.


## Giao diện chung NCTT + Thumbnail

Chạy `run.bat` hoặc `python app.py` ngay trong TOOL NCTT để mở giao diện đang dùng tại TOOL THUMBNAIL, gồm ba tab: Nghiên cứu thị trường, Làm thumbnail, Trạng thái & lịch sử. `studio.py` nạp trực tiếp `../TOOL THUMBNAIL/integrated_app.py`, nên hai điểm khởi chạy dùng cùng giao diện và bộ điều khiển Flow, không sao chép mã thumbnail.

Giữ hai thư mục TOOL NCTT và TOOL THUMBNAIL cạnh nhau. API key, quota và kết quả nghiên cứu vẫn lưu trong TOOL NCTT; cấu hình, lịch sử và ảnh tạo bằng Flow tiếp tục dùng vị trí của TOOL THUMBNAIL. Các bộ lọc Shorts và chèn thumbnail trong Excel vẫn có trong tab nghiên cứu. Mở giao diện không tự chạy nghiên cứu hoặc gửi yêu cầu tạo ảnh.

Nếu chỉ cần giao diện nghiên cứu độc lập: `python app.py --research-only`.
