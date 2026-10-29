# Flow TXT Runner

**Muốn dùng Chrome đang đăng nhập:** xem [hướng dẫn tiện ích Chrome](chrome-extension/README.md). Tiện ích chạy ngay trong tab Flow hiện có; không cần mở trình duyệt riêng. Bản Python dưới đây vẫn giữ để dùng tùy chọn.

Ứng dụng Windows/Python đọc prompt UTF-8 từ TXT và thao tác Google Flow qua trình duyệt. Không cần Gemini API key. Việc tạo ảnh vẫn sử dụng quota/credit Flow của tài khoản, không tạo thêm lượt miễn phí.

## Khởi động

1. Chạy `start.bat`. Lần đầu cần Internet để cài Playwright và Chromium trong môi trường Python riêng.
2. Bấm **Mở Google Flow**, đăng nhập bằng tài khoản của bạn. Mở dự án, chọn chế độ **Ảnh**, model, tỉ lệ và số ảnh mỗi prompt ngay trên Flow.
3. Chọn file TXT và thư mục lưu. Mặc định mỗi dòng không rỗng là một prompt. Với prompt nhiều dòng, chọn chế độ ngăn cách bằng dòng chỉ chứa `---`.
4. Cấu hình bộ chọn giao diện bên dưới. Số ảnh trong tool phải bằng số ảnh đang chọn trên Flow.
5. Bấm **Chạy lần lượt**. Tool chỉ chuyển sang prompt tiếp theo khi đã tải xong ảnh của prompt hiện tại.

## Trạng thái tích hợp và cấu hình một lần

Đây là bản triển khai có cấu hình, CHƯA kiểm thử đầu-cuối với tài khoản Flow đăng nhập. Bộ chọn mặc định ô nhập/nút tạo chỉ là ứng viên; phải xác minh trên giao diện hiện tại. Bộ chọn thẻ ảnh cố ý để trống để tránh tải nhầm ảnh cũ.

Trong DevTools của trình duyệt (F12 → Elements), xác định container lặp lại cho từng kết quả ảnh. Điền CSS selector ổn định của container vào **Thẻ chứa MỘT ảnh**. Mỗi container phải chứa đúng một ảnh kết quả và nút tải tương ứng. Dùng class/data attribute ổn định, không dùng selector vị trí `nth-child` hoặc ID chỉ có ở ảnh cũ. Tránh chọn avatar, ảnh tham chiếu hay toàn bộ lưới ảnh. **Ảnh trong thẻ** mặc định là `img`.

Điền selector ô prompt và nút tạo sao cho mỗi selector chỉ khớp một phần tử hiển thị. **Nút tải trong thẻ** là selector tương đối trong container. Nếu bấm nút mở menu, điền selector mục tải ảnh mong muốn vào **Mục tải sau menu**; nếu tải trực tiếp, để trống. Có thể dùng Playwright selector `button:has-text("...")`. Cấu hình được lưu trong `settings.json`.

Tool nhận diện ảnh mới qua URL `src` chưa xuất hiện trước khi gửi prompt, chờ ảnh tải đầy đủ và có kích thước ít nhất 256 × 256. Giao diện dùng canvas/background-image hoặc tái sử dụng cùng URL ảnh cần điều chỉnh mã tích hợp. Chỉ giữ một tab Flow và không tạo ảnh thủ công trong lúc chạy. Thẻ kết quả phải còn được render trên trang.

## Lỗi và chạy tiếp

Mỗi lần chạy có thư mục riêng, tên ảnh `0001_01.png` (đuôi theo file gốc), nhật ký `progress.json` và ảnh chụp `error.png` nếu lỗi. Tool dùng nút tải của Flow để lấy file được Flow cung cấp, không lưu ảnh thumbnail từ DOM.

Khi timeout, lỗi tải, hết quota, đăng nhập hết hạn hoặc cần CAPTCHA, tool dừng và không tự gửi lại. Xử lý trên trình duyệt rồi kiểm tra `progress.json`. Prompt `needs_review` có thể đã tạo hoặc tải một phần: kiểm tra thủ công trước khi chọn số bắt đầu, vì chạy lại có thể tiêu tốn thêm lượt. Dừng không hủy tác vụ đã gửi cho Google; thao tác tải đang chờ có thể mất tối đa 30 giây trước khi dừng.

Nếu Google không cho đăng nhập trong trình duyệt tự động, tool chưa thể tiếp tục phiên đó; cần chọn cách đăng nhập/trình duyệt được Google chấp nhận, không vượt xác minh. Thư mục `browser-profile` chứa phiên đăng nhập, không chia sẻ thư mục này.
