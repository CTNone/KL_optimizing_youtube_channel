# NCTT + Thumbnail — Desktop 1.0

**Desktop hiện điều khiển Chrome trực tiếp, không đi qua extension.** Hướng dẫn hiện tại: [DESKTOP.md](DESKTOP.md). Đóng ứng dụng cũ và mở lại shortcut NCTT + Thumbnail; bấm Mở Google Flow, đăng nhập ở cửa sổ Chrome của Desktop, chọn ảnh/prompt rồi bấm Tạo ảnh trực tiếp trên Flow.

Các mô tả bên dưới chỉ áp dụng lối chuyển dữ liệu sang extension trước phiên bản Desktop 1.0; không cần thực hiện các bước nhận từ NCTT hoặc tải lại extension khi dùng Desktop trực tiếp.

Desktop có bố cục ba cột: thư viện ảnh với tìm kiếm/cuộn, preview và prompt, cài đặt và chuyển sang Flow. Extension có thêm chọn ảnh trực tiếp PNG/JPG/WebP tối đa 4MB. Sau khi chọn ảnh (hoặc nhận NCTT), file JPEG tham chiếu được chuẩn bị trong native-host/reference-cache theo hash, giữ file nguồn nguyên vẹn. Chrome debugger tải file thật vào input hoặc chặn hộp chọn file của nút Tải nội dung lên; tool xử lý Thêm vào câu lệnh và xác nhận preview nhỏ mới bên cạnh prompt trước khi gửi. Cache tham chiếu được giữ để phục hồi sau F5. Cần đóng panel cũ, tải lại extension và mở lại ứng dụng Desktop.

Kiểm thử bổ sung đã đạt: bộ chọn tài nguyên theo screenshot (+ → tải lên → thêm vào câu lệnh), fileChooser của Chrome, ghi file tham chiếu thật, giao diện Desktop và tìm kiếm. Chưa kiểm thử upload trực tiếp trên Flow đăng nhập của người dùng.

Mở shortcut **NCTT + Thumbnail** trên Desktop. Ứng dụng dùng trực tiếp App của `../TOOL NCTT/app.py`, giữ nguyên logic nghiên cứu, quota, API key và báo cáo. Tab nghiên cứu dùng các widget gốc; tab thumbnail dùng Tkinter/ttk cùng giao diện. Không sao chép API key sang extension và không sửa mã/dữ liệu của NCTT.

## Sử dụng

1. Tải lại Flow TXT trong chrome://extensions, đóng panel cũ để native host khởi động lại. Phiên bản extension **0.9.0**.
2. Chrome Default giữ một tab dự án Flow đang đăng nhập.
3. Trong tab **Làm thumbnail**, làm mới danh sách ảnh: đọc `TOOL NCTT/thumbnails` và các thư mục kết quả trong `TOOL NCTT/exports`. Chọn ảnh để xem trước hoặc chọn **Chỉ dùng prompt**.
4. Nhập prompt, mô hình và số ảnh. Với ảnh mẫu, mô tả rõ yếu tố muốn tham khảo và ý tưởng riêng. Ví dụ: “Create a 4:3 cozy Christmas jazz café. Use the attached image as a reference for composition and lighting, with new details and no copied text. Keep essential subjects within the upper 70%; the bottom 30% is simple foreground for a later 16:9 crop.”
5. Bấm **Chuyển prompt + ảnh sang Flow TXT**. Panel Flow TXT mở hoặc được đưa lên trước.
6. Bấm **Nhận prompt + ảnh từ NCTT** trên panel, kiểm tra ảnh xem trước, prompt, mô hình, số ảnh và thư mục lưu; bấm **Tạo ảnh**.
7. Tool F5, áp dụng cài đặt, tải ảnh tham chiếu, xác nhận có ảnh đính kèm mới rồi gửi. Giữ luồng tải 2K và lưu gốc + 16:9 như trước.

## Liên kết và giới hạn hiện tại

Yêu cầu nằm cục bộ tại `chrome-extension/native-host/nctt-job.json`, một yêu cầu chờ tại một thời điểm. Chỉ xóa sau khi extension nhận và xác nhận đúng ID. Không cần web server/cổng mạng. Native host chỉ nhận ảnh nằm trong TOOL NCTT, chuyển ảnh tham chiếu thành JPEG tối đa 2048px và 4MB để truyền an toàn; file mẫu gốc giữ nguyên.

Giao diện Tkinter và panel Chrome nối bằng chuyển dữ liệu, chưa nhúng Chrome bên trong Tkinter. Tạo ảnh vẫn dùng một bộ điều khiển extension. Việc đổi account thực hiện thủ công trong Chrome; hạn mức mô hình hiện còn dùng chung hồ sơ Chrome như trước.

Upload dùng duy nhất input file chấp nhận ảnh và xác nhận preview mới tại vùng composer. Nếu Flow chưa dựng input hoặc dựng giao diện khác, tool dừng trước khi gửi; mở mục thêm ảnh trên Flow và kiểm tra lại. Chưa kiểm thử upload trực tiếp trên Flow đăng nhập; bộ test mô phỏng xác nhận trình tự upload → preview → gửi. Kiểm thử Python xác nhận chuyển ảnh/prompt, giới hạn đường dẫn, ID xác nhận, bảo toàn yêu cầu đang chờ. Kiểm thử giao diện thực dựng thành công hai tab rồi đóng, không gọi nghiên cứu hoặc Flow.

Khởi chạy thủ công bằng `Start-Studio.ps1`. Cần Python với tkinter, requests, openpyxl và Pillow (đã có trên Python 3.13 của máy hiện tại). Giữ hai thư mục TOOL NCTT và TOOL THUMBNAIL cạnh nhau; di chuyển chúng thì cập nhật shortcut. Lối chạy NCTT cũ bằng run.bat vẫn sử dụng được.
