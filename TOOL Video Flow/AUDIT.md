# Rà soát sản phẩm — 07/10/2026

Đã sửa mã và kiểm thử, ưu tiên tải video. Sau rà soát cục bộ, đã kiểm tra trên Google Flow thật theo yêu cầu của người dùng: tải một ảnh lên, gửi prompt một lần, tạo video và tải MP4 1080p thành công.

| Hạng mục | Phát hiện và xử lý |
| --- | --- |
| Nhận clip hoàn tất | Không yêu cầu player đã tải duration; phân biệt clip cũ theo nguồn và nhãn prompt đúng hàng kết quả. |
| Mở clip | Mở lần lượt, xác nhận nguồn trong preview; bổ sung overlay Angular và kích thước chiều cao cho video dọc. |
| Nút tải | Nhận mat-icon/google-symbols/file_download, tách biểu tượng khỏi tên lựa chọn. |
| Mức tải | Đọc menu và chọn mức cao nhất khả dụng; bỏ disabled, khóa và yêu cầu nâng cấp. Bấm dòng tương tác thay vì nhãn con. |
| Download chậm | Thông báo tiến độ chuẩn bị file; một lần bấm tải, hủy chờ thì hủy tác vụ con. |
| Lưu file | .part → kiểm tra header video, kích thước và SHA-256 → đổi tên; thử ghi lại trên cùng artifact đã tải. |
| Phục hồi | Tên file gắn nguồn/index, metadata để nhận lại file đã lưu; khôi phục URL hiện tại theo nguồn/prompt; không gửi prompt mới. |
| Tải một phần | Ghi theo vị trí clip thay vì append; không làm lệch clip còn thiếu. |
| Trở về UI | Escape/Đóng overlay, xác nhận và focus prompt; giữ cảnh báo vào lịch sử nếu không xác nhận được. |
| Lịch sử | Ghi JSON nguyên tử; giữ dòng được chọn khi tự làm mới, hiển thị lỗi/cảnh báo. |
| Giao diện | 800×520 có ảnh vẫn cuộn tới nút; profile Video/Thumbnail đồng bộ. |
| Khởi chạy | Launcher báo lỗi, giữ log và chặn mở trùng bản Studio mới bằng named mutex. |

Kiểm chứng: 15 unit tests; Chrome localhost toàn luồng từ monitor thật, gửi một lần, hai clip lazy-load, tải 4K trong menu giả lập, xác minh file/hash, phục hồi không phát sinh tải lần hai; menu/thiết lập/nút gửi và mức khóa; UI smoke test. Kiểm thử hủy trong lúc chờ download đã đạt: tác vụ con được dọn và focus trở về prompt. Named mutex cũng đã kiểm tra phát hiện mở trùng.

Kiểm chứng thực tế: clip `ddf1ba14-1100-4056-99e3-7e712e6feef8`, prompt “tuyết rơi.”, Veo 3.1 - Lite, Thành phần, 16:9, x1. Tài khoản cho phép 1080p, 4K bị khóa. File tải thật có kích thước 23.310.045 byte, track 1920×1080, thời lượng 8 giây; có SHA-256 và metadata trong lịch sử. Tải xong đã xác nhận trở về giao diện tạo, không có cảnh báo. Bằng chứng lưu tại `REAL_FLOW_RESULT.json` và lịch sử `Documents/TOOL Video Flow OUTPUT/Video/2026-10-07/13-00-20_ce8ac028/video.json`.

Các lỗi phát hiện trên Flow thật đã sửa: video hoàn tất có player ẩn; thumbnail mở trang `/edit/` thay vì dialog; menu Angular ghép chữ nhãn/caption; mục 4K khóa không được làm loại các mục 1080p/720p cùng menu; nguồn playback chuyển sang proxy sau hover. Lưu đường dẫn bản xem đã xác nhận để tải lại đúng clip khi URL phát thay đổi. Kiểm thử menu dùng HTML thật đã ghi nhận, có kiểm thử token riêng cho thumbnail/nút tải, hủy chờ tải và clip ẩn.

Giới hạn: kiểm chứng thật lần này bao phủ một ảnh, một clip 16:9, Veo 3.1 - Lite và tải 1080p trên tài khoản hiện tại. Các tổ hợp 9:16/x2–x4 và tài khoản khác chưa được kiểm chứng trực tiếp trên Google. MP4 đã đọc header, track geometry và duration; chưa kiểm tra giải mã toàn bộ khung hình.

Logic NCTT và Thumbnail được dùng lại từ hai thư mục nguồn; đã kiểm tra tích hợp/import/giao diện, không gọi nghiên cứu tốn quota hoặc generate ảnh/video mới. Hai thư mục nguồn vẫn là phụ thuộc của ứng dụng.


Cập nhật nhận diện hoàn tất: bỏ chờ ổn định 2 giây; kiểm tra kết quả mỗi 0,25 giây. Nhận clip từ thumbnail đã tải trong flow-video-tile ngay cả khi chưa mount video; tiến độ tạo dưới 100% và trạng thái đang tạo vẫn bị loại. Giữ loại clip cũ theo baseline nguồn/thumbnail và prompt. 16 unit tests, kiểm thử Chrome thumbnail-only 99%→100%, menu Flow thật đã ghi nhận và pipeline tải/hủy đều đạt. Thay đổi nhận diện này kiểm thử cục bộ; chưa tạo thêm lượt trên Google Flow.


Tách chế độ Thumbnail/Video: trước mỗi resumeRun của Thumbnail (bao gồm thử lại sau reload), StudioFlow bấm và xác nhận Hình ảnh rồi mới chuyển cho logic model/tỉ lệ/số ảnh. Video bấm và xác nhận Video trước cấu hình riêng. Menu đang mở được nhận bằng cặp Hình ảnh/Video, tránh bấm toggle đóng nhầm khi đang ở chế độ ảnh. Nếu không xác nhận mode thì không gửi lượt. 18 unit tests và Chrome fixture chuyển Video→Image→Video→Image đã đạt; không tạo thêm nội dung trên Google trong kiểm thử này.


Sửa cấu hình Thumbnail sau chuyển chế độ: nạp thumbnail-models.js và thumbnail-settings.js cục bộ sau runtime nguồn. Nhận trigger composer không cần nhãn Cài đặt, model trong portal ngoài vùng prompt, loại menu option khỏi model đang chọn; bỏ icon khỏi nhãn tỉ lệ/số ảnh, nhận aria-pressed; nếu bảng số ảnh đã mở thì bấm lựa chọn trực tiếp, không toggle đóng bảng. Chrome fixture đã chạy model Nano Banana 2 Lite → 3:4 → x2 → nhập prompt → gửi đúng một lần. Đây là kiểm thử cục bộ, chưa xác minh lượt tạo ảnh thật trong lần sửa này.
