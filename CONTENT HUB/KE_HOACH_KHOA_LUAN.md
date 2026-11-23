# Kế hoạch hoàn thiện và đánh giá khóa luận

## Luận điểm kỹ thuật

Đề tài: **Phát triển hệ thống quản trị quy trình sản xuất nội dung trên nhiều kênh
YouTube**. Đối tượng thử nghiệm: một người vận hành nhiều kênh. Đóng góp là mô hình dữ
liệu phân cấp kênh → album phát hành → video/mix, quy trình có hướng dẫn nhưng cho phép
ngoại lệ có audit, truy xuất nguồn/phiên bản, QC gắn đúng bản, handoff công cụ và theo
dõi hiệu suất sau đăng bằng dữ liệu YouTube thật.

Google Flow, CapCut, NCTT và Music Manager là công cụ được tích hợp hoặc mở theo ngữ
cảnh. Hub không tự sinh nội dung, không render video và không tự đăng YouTube; không
tuyên bố cải thiện nhân quả lượt xem/doanh thu.

## Ưu tiên theo vấn đề thực tế

| Vấn đề | Giải pháp trong Hub | Cách kiểm chứng |
|---|---|---|
| Dễ nhầm file giữa kênh/album | `project_id`, `channel_id`, `album_id` xuyên suốt | Lọc kênh/album, mở đúng nguồn, xuất hồ sơ |
| Không nhớ bản nào đã duyệt | QC gắn `asset_id`/version thành phẩm | Đổi file sau QC, xác nhận bắt duyệt lại |
| Chuyển tool mất ngữ cảnh | Brief, tài nguyên, handoff theo dự án | Mở đúng thư mục dự án và đúng kênh |
| Quy trình thực tế có ngoại lệ | Đổi Bước tay có audit `manual`/`override` | So sánh gate tuần tự và thao tác tay |
| Báo cáo dựa vào cảm tính | Audit, hồ sơ JSON, snapshot Analytics | Đối chiếu thao tác, thời điểm và nguồn |
| Không biết video nào tốt/kém | Bảng video đã đăng: views, CTR, AVD, retention | So sánh nhiều video cùng kênh sau khi có dữ liệu thật |
| Nhiều kênh khác email | Mỗi kênh một token OAuth và snapshot riêng | Kết nối/ngắt từng kênh, kiểm tra dữ liệu cách ly |

## Phạm vi đã chốt

**Trong phạm vi bảo vệ:** phân cấp kênh/album/video; brief và trạng thái; gate tuần tự
và đổi bước tay có audit; tài nguyên có hash/version; QC gắn đúng file; lịch nội bộ và
URL/ngày đăng; handoff NCTT/Music/Flow; audit và xuất hồ sơ; analytics video/kênh cho
5 kênh; demo tách database.

**Đã bỏ khỏi phạm vi:** render/FFmpeg/Tool Edit trong Hub; playlist nhạc riêng từng video
trong Hub. Playlist vẫn do Music Manager quản lý; CapCut vẫn là nơi biên tập.

**Ngoài phạm vi:** RBAC/cộng tác mạng, tự đăng YouTube, AI SEO/planner, chatbot Flow
riêng, thêm provider sinh nội dung.

## Kịch bản bảo vệ 10–15 phút

1. Nêu vấn đề dữ liệu/quy trình phân tán và giới thiệu kiến trúc.
2. Mở DB demo: 3 kênh, 6 album, 12 video/mix; lọc theo kênh.
3. Mở một album có hai video, cho thấy brief và trạng thái riêng.
4. Thử chuyển bước tuần tự khi thiếu tài nguyên để thấy gate.
5. Đổi Bước bằng menu chuột phải, mở Lịch sử để thấy audit `manual`/`override`.
6. Mở handoff, trình bày Flow/NCTT/Music Manager và cách nhập kết quả thủ công.
7. Nhập một video hoàn chỉnh, duyệt checklist QC, thử thay file để thấy duyệt cũ mất hiệu lực.
8. Nhập link YouTube và ngày đăng ngay tab Thông tin.
9. Mở Analytics: chọn kênh, kết nối OAuth, làm mới video/kênh; so sánh bảng video.
10. Trình bày backup, xuất hồ sơ và phân biệt dữ liệu demo với dữ liệu thật.

## Thiết kế thực nghiệm

Chuẩn bị tối thiểu ba kênh thử nghiệm, mỗi kênh 2–3 album với nhiều video/mix. Dùng cùng
bộ nguồn cho quy trình thủ công và Hub. Tách thời gian thao tác người dùng, thời gian
chờ dịch vụ và độ trễ báo cáo YouTube.

Thu thập:

- Thời gian tìm đúng nguồn/phiên bản và xác định trạng thái.
- Số thao tác chuyển tool/ghi thông tin và số lỗi gắn nhầm tài nguyên.
- Số ca gate từ chối đúng và số ca phải override; lý do override trong audit.
- Số lần QC phải duyệt lại sau khi file thay đổi.
- Thời điểm lấy snapshot, khoảng ngày dữ liệu và độ trễ CTR.
- Tỷ lệ hoàn thành trên tập thử nghiệm đã mô tả; không suy rộng ra mọi nội dung.

Công thức giảm thời gian thao tác: `(T_thủ_công - T_hệ_thống) / T_thủ_công × 100%`.
Chỉ điền số sau khi đo; chưa có bằng chứng để tuyên bố tăng năng suất.

Ghi từng lượt và lưu bằng chứng theo [phiếu thực nghiệm khóa luận](PHIEU_THU_NGHIEM_KHOA_LUAN.md).
Database demo 3 kênh/6 album/12 video là dữ liệu minh họa giao diện, không dùng làm kết
quả đo quy trình thực tế.

## Lộ trình còn lại

1. **Hoàn tất Analytics:** nhập 5 channel ID, kết nối OAuth thật, xác nhận quyền từng
   kênh, tạo reporting job, kiểm tra CSV/đơn vị CTR và độ trễ.
2. **Kiểm thử vận hành:** đi hết một dự án thật, ghi vướng mắc, chỉ sửa lỗi chặn luồng.
3. **Đóng băng phạm vi:** không thêm render/playlist/SEO/tự đăng; chỉ sửa lỗi dữ liệu,
   mất trạng thái, gắn nhầm tài nguyên hoặc sai lệch hiển thị.
4. **Đánh giá và viết báo cáo:** use case, ERD, sequence, kiểm thử, thực nghiệm, giới hạn.

## Mốc triển khai

| Thời gian | Trọng tâm | Kết quả phải có |
|---|---|---|
| 23–30/11/2026 | Chốt Analytics và dữ liệu sạch | 5 kênh có channel ID; một lần kết nối thật; snapshot video/kênh chạy; demo 3/6/12 |
| 01–07/12/2026 | Chạy thử nghiệm có kịch bản | Bộ số đo, ảnh/log, kịch bản bảo vệ chạy từ đầu đến cuối |
| 08–14/12/2026 | Đóng băng và đóng gói | Bản ứng viên, hướng dẫn chạy, kết quả kiểm thử, giới hạn rõ ràng |
| 15/12 đến bảo vệ | Chỉ sửa lỗi nghiêm trọng | Không thêm tính năng; có DB và bản demo dự phòng |

## Dàn ý báo cáo

1. Tổng quan bài toán và công cụ liên quan.
2. Khảo sát nghiệp vụ, phạm vi, yêu cầu chức năng/phi chức năng.
3. Phân tích thiết kế: kiến trúc, dữ liệu, workflow, sequence và quyết định kỹ thuật.
4. Cài đặt và tích hợp: Store, adapter, UI, OAuth/Analytics.
5. Kiểm thử, thực nghiệm, kết quả và phân tích giới hạn.
6. Kết luận và hướng mở rộng.

## Cổng phát hành

- Tạo/sửa/lọc ít nhất ba kênh; video thuộc đúng album.
- Gate tuần tự từ chối khi thiếu điều kiện; đổi bước tay có audit.
- Thay file sau QC; duyệt cũ không còn hợp lệ.
- Nhập URL/ngày đăng; Analytics dùng đúng ngày và đúng kênh.
- Kết nối/ngắt một kênh không ảnh hưởng kênh khác.
- Xuất hồ sơ, backup database, chạy demo trên môi trường sạch.
- Lưu ảnh chụp, log, dữ liệu đầu vào, phiên bản phần mềm cho từng ca.
