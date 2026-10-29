# Kế hoạch hoàn thiện và đánh giá khóa luận

## Luận điểm kỹ thuật

Đề tài giữ tên: **Phát triển hệ thống quản trị quy trình sản xuất nội dung trên nhiều
kênh YouTube**. Đối tượng thử nghiệm: một người vận hành nhiều kênh. Đóng góp là mô
hình dữ liệu và quy trình, truy xuất nguồn/phiên bản, QC, điều phối render, phục hồi
và kết nối công cụ. Google Flow là dịch vụ được tích hợp; không tuyên bố tự phát
triển mô hình sinh ảnh/video hoặc tự cải thiện hiệu quả kinh doanh của kênh.

## Brainstorm đã chuyển thành ưu tiên

| Vấn đề thực tế | Giải pháp sản phẩm | Cách kiểm chứng |
|---|---|---|
| Dễ nhầm file giữa các kênh | Mỗi nội dung có project_id và channel_id | Tạo hai kênh, lọc và xuất hồ sơ riêng |
| Không nhớ bản nào đã duyệt | QC gắn version thành phẩm | Đổi file sau QC, xác nhận bắt duyệt lại |
| Chuyển tool làm mất ngữ cảnh | Brief, nguồn và handoff theo dự án | Mở editor_project.json với đúng clip |
| Render lỗi khó tìm nguyên nhân | Job snapshot, log, lỗi và retry_of | Cố ý thiếu/sửa nguồn rồi thử lại |
| Đóng app không biết render xong chưa | Interrupted và kiểm tra output | Dừng thử nghiệm, mở lại DB demo |
| Báo cáo dựa vào cảm tính | Nhật ký và hồ sơ xuất JSON | Đối chiếu thao tác, thời gian và nguồn |

## Kịch bản bảo vệ 10–15 phút

1. Nêu vấn đề dữ liệu và quy trình phân tán; giới thiệu kiến trúc.
2. Mở DB demo, thể hiện hai kênh khác phong cách.
3. Mở dự án, brief và trạng thái; thử chuyển bước khi thiếu nguồn để thấy gate.
4. Mở thư mục handoff, trình bày liên kết với Studio và editor đang có.
5. Render bản ngắn (ví dụ 0.1 phút = 6 giây) bằng clip mẫu đã chuẩn bị.
6. Hiển thị job, hash và thành phẩm; chuyển QC, duyệt checklist.
7. Nhập bản mới để minh họa vô hiệu hóa trạng thái duyệt.
8. Trình bày lịch đăng nội bộ, snapshot chỉ số và xuất hồ sơ.
9. Dùng video 1 giờ đã render trước làm bằng chứng thời lượng, không chờ render dài
   trong buổi bảo vệ. Phân biệt dữ liệu minh họa và dữ liệu thật.

## Thiết kế thực nghiệm đề xuất

Chuẩn bị tối thiểu hai kênh thử nghiệm, mỗi kênh 3–5 dự án. Dùng cùng bộ nguồn cho
quy trình thủ công và Hub. Tách thời gian thao tác của người dùng, thời gian máy xử
lý và thời gian chờ dịch vụ. Không so một lượt thủ công đầy đủ với một lượt Hub dùng
cache mà không ghi rõ điều kiện.

Thu thập:

- Thời gian tìm đúng nguồn/phiên bản, bàn giao và xác định trạng thái.
- Số thao tác chuyển tool/ghi thông tin và số lỗi gắn nhầm tài nguyên.
- Thời gian render, cấu hình máy, độ phân giải, codec, dung lượng và thời lượng nguồn.
- Tỷ lệ hoàn thành trên tập thử nghiệm đã mô tả; không suy rộng ra mọi nội dung.
- Các ca lỗi thiếu file, nguồn bị sửa, hủy, chạy lại và khởi động lại.
- QC điểm nối từ preview nhiều vòng; người đánh giá, tiêu chí và kết quả.

Công thức giảm thời gian thao tác: `(T_thủ_công - T_hệ_thống) / T_thủ_công × 100%`.
Chỉ điền số sau khi đo; chưa có bằng chứng để tuyên bố tỷ lệ tăng năng suất.

## Lộ trình tiếp theo

1. **Kiểm thử vận hành với dữ liệu thật:** đi hết một dự án, ghi vướng mắc, điều chỉnh UI.
2. **Bàn giao tự động có định danh:** bổ sung project_id vào request/manifest Studio,
   nhập kết quả theo ID chính xác; không dùng “file mới nhất” làm bằng chứng.
3. **Báo cáo theo kênh:** tổng hợp snapshot mới nhất và tiến độ tuần; phân biệt số tích
   lũy và số trong kỳ. Chỉ nối YouTube API khi đã chốt nhu cầu và xác thực.
4. **Đánh giá và viết báo cáo:** use case, ERD, sequence job/QC, test, thực nghiệm,
   giới hạn và hướng phát triển. Không mở thêm phân hệ trước khi quy trình chính ổn.

## Dàn ý báo cáo gợi ý

1. Tổng quan bài toán và công cụ liên quan.
2. Khảo sát nghiệp vụ, phạm vi, yêu cầu chức năng/phi chức năng.
3. Phân tích thiết kế: kiến trúc, dữ liệu, workflow, sequence và quyết định kỹ thuật.
4. Cài đặt và tích hợp: Store, adapter, queue, media engine và UI.
5. Kiểm thử, thực nghiệm, kết quả và phân tích giới hạn.
6. Kết luận và hướng mở rộng.

Các chỉ số YouTube chỉ là dữ liệu vận hành tham khảo. Hiệu quả views/doanh thu không
phải tiêu chí duy nhất để đánh giá chất lượng phần mềm và chưa có thiết kế nhân quả
để quy kết tăng trưởng kênh cho Hub.
