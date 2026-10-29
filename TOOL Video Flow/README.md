# YouTube Music Studio

Mở shortcut **NCTT + Thumbnail** trên Desktop. Shortcut đã chuyển sang `Start-Studio.ps1` của TOOL Video Flow.

- NCTT và Thumbnail dùng lại logic của hai thư mục TOOL NCTT và TOOL THUMBNAIL; giữ hai thư mục này cạnh TOOL Video Flow.
- Lịch sử có bộ lọc NCTT / Thumbnail / Video, gom ngày và giờ từng lượt, hiển thị chi tiết và mở thư mục kết quả. Tự làm mới mỗi 5 giây.
- NCTT mới: `TOOL Video Flow OUTPUT/NCTT/YYYY-MM-DD/HH-MM-SS_id`. Thumbnail mới: `TOOL Video Flow OUTPUT/Thumbnail/YYYY-MM-DD/HH-MM-SS_id`. Video mới: `TOOL Video Flow OUTPUT/Video/YYYY-MM-DD/HH-MM-SS_id`.
- Dữ liệu cũ giữ nguyên vị trí. Lịch sử Thumbnail đọc state.json của từng hồ sơ trong TOOL THUMBNAIL, NCTT cũ đọc thư mục exports. Lượt NCTT không có báo cáo được ghi là chưa có báo cáo, không suy đoán thành công.
- Video có tạo tự động từ một ảnh + prompt, xác nhận cài đặt, chờ kết quả và chọn độ phân giải tải cao nhất khả dụng. Có thể lưu bản chuẩn bị riêng; bản chuẩn bị không được ghi là video đã tạo.

Kiểm tra: biên dịch Python, dựng giao diện bốn tab, thư mục từng lượt không trùng và chuyển thời gian UTC sang UTC+7. Chưa chạy nghiên cứu tốn quota hoặc tạo ảnh/video trên phiên Google thật.

## Tạo video

Đóng Studio cũ rồi mở lại shortcut Desktop. Kết nối Chrome và chọn đúng tab dự án Flow ở tab Thumbnail (hoặc mở hồ sơ Desktop). Trong tab Video, chọn một ảnh, nhập prompt, chọn Thành phần/Khung hình, 16:9/9:16, đúng tên mô hình Flow và x1–x4, rồi bấm Tạo video.

Bộ điều khiển Video dùng lại kết nối Chrome, F5/chờ, upload ảnh và xác nhận ảnh đính kèm của Thumbnail. Cài đặt phải được xác nhận trước khi gửi. Sau một lần gửi, chờ đủ video mới có thể phát và ổn định 8 giây, tối đa 20 phút. Menu tải được đọc để chọn mức cao nhất khả dụng theo số pixel (ví dụ 4K > 1080p > 720p); không cố định một mức. Chờ download/upscale tối đa 15 phút. Không tự gửi lại khi không rõ kết quả. Dừng chỉ dừng thao tác tool; tác vụ Google đã nhận có thể tiếp tục tạo.

Kết quả và video.json nằm dưới `TOOL Video Flow OUTPUT/Video/ngày/giờ_id`, kèm ảnh đầu vào, prompt, cài đặt, trạng thái, mức tải và đường dẫn file đã lưu. File tải một phần được giữ nếu video tiếp theo gặp lỗi.

Đã kiểm thử cài đặt bằng Chrome thật trên trang giả lập cục bộ, thứ tự độ phân giải, không gửi lại khi chưa xác nhận, biên dịch và giao diện. Chưa kiểm chứng trọn luồng trên Flow đăng nhập thật: nếu Flow đổi nút, hiển thị video qua preview khác hoặc menu tải khác, tool sẽ báo lỗi và cần cập nhật nhận diện. Chưa dùng credit của người dùng để tạo video thử.

Tab Video có thanh cuộn toàn trang (kéo thanh bên phải hoặc lăn chuột ngoài ô prompt), và thanh cuộn riêng cho prompt. Đã kiểm tra cửa sổ 800×520 với ảnh xem trước: cuộn tới cuối vẫn thấy nút Tạo video.

Quét hồ sơ Chrome tự động khi mở ứng dụng, có Quét lại / Kết nối Chrome đang mở / Nhập phiên / Mở Flow bằng hồ sơ Desktop ngay trong tab Video. Video và Thumbnail dùng chung lựa chọn và bộ kết nối. Phiên đã đăng nhập được dùng lại khi còn hiệu lực; Google yêu cầu đăng nhập hoặc Allow thì người dùng thực hiện trong Chrome. Kiểm tra máy hiện tại tìm được 3 hồ sơ Chrome.

Mục Vị trí lưu video sau khi tải ở tab Video cho phép chọn thư mục bên trong `TOOL Video Flow OUTPUT` và nhớ lựa chọn qua video-settings.json. Mặc định là `TOOL Video Flow OUTPUT/Video/ngày/giờ_id`. video-runs.json giữ danh sách lượt để lịch sử đọc được các kết quả đã lưu.

Menu mô hình được chờ sau khi mở, nhận diện tên Veo tách khỏi mô tả/credit, hỗ trợ dấu -, – và —, dòng lựa chọn dạng div như logic Thumbnail. Kiểm thử Chrome giả lập bao gồm menu xuất hiện chậm, dòng mô hình có mô tả và xác nhận tên sau chọn.

Sửa tích hợp bộ theo dõi lỗi: FlowErrors.watch nhận object {visible, prompt, ignoreExisting}, kiểm tra lỗi trước khi bấm gửi và trong lúc chờ. video.json ghi stage, submitAttempted, submitted, submissionUncertain và traceback; ghi bằng file tạm rồi thay thế nguyên tử. Lỗi trước khi bấm không được ghi thành đã gửi. Không tự gửi lại khi kết quả thao tác chưa rõ.

Kiểm thử bổ sung: 7 kiểm thử vòng đời (preflight, gửi một lần, thành công, tải một phần, dừng, click chưa chắc chắn, xếp độ phân giải); Chrome thật + máy chủ localhost mô phỏng toàn luồng dùng API FlowErrors thật, hai video kết quả mô phỏng và tải hai file ở lựa chọn 4K. Bộ test phân biệt lỗi cũ với lỗi credit mới. Đây là thử nghiệm cục bộ, chưa xác nhận tạo/tải video trên Google Flow thật.

Tải video: nhận diện nút download/file_download/download_2 trong card của đúng video; nếu không có, mở video rồi chờ nút tải trong bản xem đã xác nhận nguồn. Menu độ phân giải hỗ trợ dòng dạng div và chờ xuất hiện. Không chọn nút tải ở card khác.

Khi video đã tạo nhưng tải lỗi, dùng Tải lại video đã tạo… và chọn video.json của lượt đó. Tool không F5, không upload, không gửi lại prompt. Lượt mới lưu resultSources để tải lại đúng kết quả; lượt cũ thiếu mã kết quả yêu cầu chọn video đang hiển thị trên Flow. Giữ tab dự án và mở đúng kết quả cần tải. Kết quả tải lại lưu trong cùng thư mục lượt cũ.

Trình tự tải hiện giống Thumbnail: đóng bản xem cũ → bấm từng video mới → xác nhận nguồn video trong bản xem → Tải xuống → chọn mức cao nhất được phép → chờ và lưu file → đóng bản xem để sang video tiếp theo. Tùy chọn bị disabled, aria-disabled ở dòng cha, biểu tượng khóa hoặc yêu cầu nâng cấp gói bị loại trước khi xếp độ phân giải. Không mặc định tài khoản nào cũng tải được 4K.

Nhận kết quả video không còn phụ thuộc readyState>=2 hoặc duration đã tải: Flow có thể lazy-load player cho tới khi bấm clip. Tool đọc currentSrc/src/source[src], loại lỗi media và card đang xử lý, so mã nguồn với snapshot trước gửi, chờ đủ kết quả mới ổn định 2 giây rồi mở clip để xác nhận preview và tải. Nguồn chuẩn hóa tránh tính lại video cũ chỉ đổi token URL. Sau tải, Escape đóng menu/bản xem; nếu còn dialog chứa video thì bấm nút Đóng và xác nhận ô prompt để đưa focus về giao diện tạo. Kiểm thử Chrome localhost có readyState=0, duration=NaN và nguồn src sẵn có.

Sửa nhận diện kết quả trên Flow thật: grid ảo có thể đưa một clip cũ vào DOM sau khi gửi, gây đếm 2/1 và chờ vô hạn đến timeout. Snapshot trước gửi nay lấy cả video ẩn đang có; kết quả sau gửi được đối chiếu đúng nhãn prompt trong flow-grid-tile-container. Đã kiểm tra trực tiếp, chỉ đọc trên Flow của người dùng: hai clip có nhãn “tuyết rơi.” / “tuyết rơi mạnh.”, detector mới chọn đúng một clip của prompt hiện tại trong khoảng 2 giây. Kiểm tra này chưa thực hiện thao tác tải.

Nút Tải lại video đã tạo không mở hộp chọn file/thư mục nữa. Nó lấy lượt video đang chọn trong Lịch sử, hoặc lượt đã gửi gần nhất chưa tải xong. Lượt cũ thiếu resultSources được đối chiếu đúng prompt với clip trên Flow và tải tự động. Nếu đang chờ tạo video, nút này dừng bộ chờ rồi chuyển sang tải kết quả có sẵn; không gửi prompt mới. Chọn nơi lưu vẫn là nút riêng.

Đợt rà soát toàn diện 07/10/2026: xem AUDIT.md. File tải dùng .part, xác minh header/kích thước/SHA-256, tên gắn source/index và metadata để phục hồi không tải trùng. Có tiến độ chờ upscale/download và dọn tác vụ con khi hủy. Launcher mới chặn mở trùng ứng dụng; đóng bản đang mở trước khi mở shortcut để nạp thay đổi.


## Chuyển Hình ảnh / Video

Tool chọn chế độ trong cặp nút Hình ảnh–Video của bảng cài đặt, không dùng nút trùng tên ở thanh bên. Xác nhận chế độ xong mới chọn mô hình, Thành phần/Khung hình, tỉ lệ và số lượng. Sau mỗi lần bấm, tool tìm lại phần tử mới vì Flow có thể dựng lại menu; nếu Flow đóng menu thì mở lại để xác nhận. Trạng thái ARIA được ưu tiên; màu nền chỉ xác nhận nút sáng hơn các nút cùng nhóm. Chế độ đã đúng thì không bấm lại. Kiểm thử hồi quy có sidebar trùng tên, menu dựng lại/đóng sau click, đổi chế độ nhiều lần và lựa chọn chỉ thể hiện bằng màu nền. Kiểm thử dùng Chrome thật trên trang cục bộ, không tạo ảnh/video trên phiên Google thật.
