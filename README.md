# YouTube Content Hub

Đây là điểm bắt đầu cho repo khóa luận **Phát triển hệ thống quản trị quy trình sản
xuất nội dung trên nhiều kênh YouTube**.

## Chạy sản phẩm chính

Chạy [`OPEN_CONTENT_HUB.bat`](OPEN_CONTENT_HUB.bat). Để xem dữ liệu mẫu trước, chạy
[`OPEN_CONTENT_HUB_DEMO.bat`](OPEN_CONTENT_HUB_DEMO.bat). Bắt đầu vận hành với
[hướng dẫn cho người mới](CONTENT%20HUB/README.md#bắt-đầu-nhanh-cho-người-mới).

## Bản đồ thư mục

| Đường dẫn | Vai trò trong khóa luận |
|---|---|
| [`CONTENT HUB/`](CONTENT%20HUB/) | **Sản phẩm chính**: quản lý kênh, đợt phát hành, video, tài nguyên, quy trình, QC, render job và Analytics sau đăng. Xem [`AI_HANDOFF.md`](CONTENT%20HUB/AI_HANDOFF.md) trước khi tiếp tục sửa Analytics. |
| [`docs/`](docs/) | Đặc tả tổng hợp và sơ đồ khóa luận. Mục Phạm vi hiện hành (v2.0) là phạm vi có hiệu lực. |
| [`archive/`](archive/) | Tool Google Flow Agent thử nghiệm đã nghỉ khỏi luồng chính; giữ nguyên mã và dữ liệu để tham khảo. |
| [`TOOL NCTT/`](TOOL%20NCTT/) | Công cụ nghiên cứu thị trường tùy chọn, được mở theo ngữ cảnh video. |
| [`editer/Nhạc jazz/`](editer/Nhạc%20jazz/) | Thư viện nhạc và Music Manager tùy chọn. |
| [`editer/TOOL EDIT/`](editer/TOOL%20EDIT/) | Engine dựng/render được Hub tích hợp; không phải sản phẩm khóa luận riêng. |
| [`TOOL THUMBNAIL/`](TOOL%20THUMBNAIL/) | Tích hợp Flow và mã tương thích cho các luồng cũ. Không phải điểm bắt đầu của người dùng Hub. |
| [`TOOL Video Flow/`](TOOL%20Video%20Flow/) | Ứng dụng/tích hợp Flow cũ và thành phần được giữ để tương thích. Không mở nếu chỉ quản lý quy trình trong Hub. |
| [`OUTPUT TỔNG/`](OUTPUT%20TỔNG/) | Media và kết quả phát sinh tại máy; không phải mã nguồn. |

Các thư mục tool được giữ tại vị trí hiện tại vì launcher và tích hợp dùng đường dẫn
đó. Đừng di chuyển hoặc đổi tên thư mục tool nếu chưa cập nhật các adapter tương ứng.
Sơ đồ nằm trong `docs/diagrams/`; không còn để file tài liệu rời ở thư mục gốc.

## Phạm vi sản phẩm

Hub tập trung vào luồng **kênh → đợt phát hành → video/mix → tài nguyên → QC →
lịch nội bộ/xác nhận đã đăng**. Flow, nghiên cứu thị trường, nhạc và editor là dịch vụ
hoặc công cụ hỗ trợ; chúng không được xem như chức năng AI do khóa luận phát triển.

MVP là ứng dụng desktop cục bộ cho một người vận hành nhiều kênh. Tab **Theo dõi video sau
đăng** đọc Analytics qua Google OAuth theo yêu cầu, lưu snapshot cục bộ; Hub không đăng
video. SEO/AI planner, phân quyền nhóm và cộng tác mạng nằm ngoài phạm vi. Xem
[kiến trúc và phạm vi](CONTENT%20HUB/KIEN_TRUC_VA_PHAM_VI.md) và
[kế hoạch khóa luận](CONTENT%20HUB/KE_HOACH_KHOA_LUAN.md).


