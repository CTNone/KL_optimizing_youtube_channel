# Quản lý nhạc và ghi công

Nhấp đúp **Mo_Quan_Ly_Nhac.cmd** trong thư mục Nhạc jazz. Ứng dụng dùng Python/Tkinter có sẵn trên máy, không cần Internet hay đăng nhập.

1. **Thư mục nhạc** ở đầu cửa sổ cho biết thư mục đang quét. Chọn thư mục khác khi cần; **Quét lại** cập nhật ngay trạng thái tệp. Bản ghi không còn tệp được ẩn khỏi tìm kiếm thông thường và vẫn có thể xem bằng trạng thái **Thiếu tệp**.
2. Tìm theo tên/nghệ sĩ. Chọn kênh và dự án đang thao tác trên thanh lọc; bộ đếm cho biết số bài trong từng mục. Bật **Chỉ kênh hiện tại** hoặc **Chỉ dự án hiện tại** để lọc thư viện; chọn trạng thái trong **Trạng thái ghi công** để lọc theo ghi công. Bài trùng giữa nhiều thư mục vẫn dùng chung một hồ sơ ghi công.
3. Bấm **▶** đầu dòng để phát/tạm dừng; thanh phát hiển thị thời gian hiện tại/tổng thời lượng, có thể kéo để tua hoặc dùng nút ±10 giây. Bài đang phát được tô xanh, chữ đậm và hiện ở dòng trạng thái. Các hàng có nền xen kẽ để dễ dò. Nhấp đúp vào tên bài để sao chép tên. Nhấp chuột phải ở cột **Dự án** hoặc **Kênh** để chọn trực tiếp mục cần thêm/bỏ cho bài đó; ở cột **Ghi công** để chọn trạng thái. Menu chuột phải có **Xóa bài và tệp nhạc gốc**; xác nhận sẽ xóa mọi bản sao đã quét của bài và gỡ bài khỏi dự án/kênh. Nhấp chuột phải ở phần khác của dòng để đặt trạng thái hoặc mở hồ sơ chi tiết. Khi đặt Cần ghi công, nhập nguyên văn nội dung trước khi lưu.
4. Dùng **Dự án mới**, chọn dự án hiện tại rồi thêm bài bằng menu chuột phải. **Xuất CapCut** tạo gói mới trong `OUTPUT TỔNG/Music Manager/CapCut_Exports`, gồm `Audio`, `GHI_CONG.txt`, `CAN_KIEM_TRA.txt`, danh sách CSV và bản chụp JSON. Bài chưa kiểm tra được liệt kê trong gói nháp; bài thiếu tệp không thể xuất. **Xuất CapCut · chuẩn hóa** tạo MP3 riêng cho mọi bài trong dự án, nhắm -14 LUFS và -2 dBTP để chừa khoảng an toàn cho mã hóa MP3, cắt im lặng đầu/cuối rồi chừa 0,3 giây yên lặng ở trước và sau phần âm thanh. Cần cài FFmpeg và có `ffmpeg.exe` trong `PATH`. Tệp nguồn không bị chỉnh sửa.
5. **Lịch sử** ghi các lần sửa hồ sơ, thay đổi dự án/kênh, quét thư viện và xuất gói. Chọn một bài rồi mở lịch sử trong cửa sổ ghi công để xem riêng lịch sử bài đó.

Kênh được lấy trực tiếp từ `CONTENT HUB/data/content_hub.sqlite3`; hãy tạo/sửa kênh trong Content Hub. Music Manager gán nhạc bằng ID kênh Hub và lưu playlist cùng database. Trong **Tool Edit**, tab **Audio & Playlist** chọn cùng tên kênh. Bấm **Làm mới playlist từ Music Manager** nếu vừa thay đổi danh sách khi Editor đang mở.

Khi mở Music Manager từ một video/mix trong Content Hub, ứng dụng chọn sẵn kênh
tương ứng. Nếu video đã gắn playlist, playlist đó cũng được chọn; việc mở ứng dụng
không tự sửa playlist, thêm bài hoặc xuất gói.

Gói hoàn chỉnh yêu cầu mọi bài đã được kiểm tra và bài cần ghi công có nội dung. Bạn có thể chủ động xuất bản nháp để dựng video khi chưa kiểm tra xong; bản nháp có danh sách cần xử lý. Bài thiếu tệp không thể xuất. Khi đăng video, dán nội dung GHI_CONG.txt vào mô tả theo yêu cầu của giấy phép bạn đã kiểm tra.

Các bài trùng giữa nhóm chỉ xuất một lần trong một dự án. Mỗi lần xuất tạo một thư mục mới, giữ nguyên gói cũ để truy vết. Nếu bạn đổi danh sách hoặc thông tin ghi công, hãy xuất lại và dùng gói mới. Nội dung ghi công trong gói cũ không tự cập nhật.

## Dữ liệu và sao lưu

- Ứng dụng lưu thư mục quét đã chọn trong `OUTPUT TỔNG/Music Manager/library_path.txt`. Ngoài thư mục đó, ứng dụng vẫn quét `OUTPUT TỔNG/Music Library/Tracks`. Bài được sao chép khi xuất.
- Thư viện, ghi công và quan hệ bài–kênh nằm trong `CONTENT HUB/data/content_hub.sqlite3` cùng dự án Hub. Dữ liệu có sẵn trong `Music_Manager/data/music.sqlite3` được sao chép một lần khi mở Music Manager; database cũ được giữ nguyên làm bản nguồn.
- Sao lưu tự động khi mở ứng dụng vào `OUTPUT TỔNG/Music Manager/Backups`.
- Để khôi phục: đóng ứng dụng, sao chép bản sao lưu mong muốn thành `data/music.sqlite3` (giữ bản hiện tại riêng trước).
- Quét lại thư viện sau khi thêm/xóa/di chuyển nhạc. Dữ liệu ghi công và dự án đã lưu được giữ lại. `.audio_cache` và các gói xuất không được quét thành nhạc nguồn.
- Nguồn metadata ban đầu là `OUTPUT TỔNG/Music Library/library_audit.json` đã đối chiếu Excel (có hỗ trợ đọc tệp audit cũ trong thư mục nhạc). Tệp nhạc mới được nhận dạng theo tên `Tên bài - Nghệ sĩ`; nếu thiếu nghệ sĩ, hiển thị Chưa xác định. Tên sai cần được sửa ở tệp nguồn rồi quét lại; hồ sơ của tên cũ vẫn giữ để tránh mất dữ liệu.
- Tất cả bài khởi đầu là **Chưa kiểm tra**. Không tự suy luận trạng thái từ tệp Excel, cookie hoặc nội dung tài liệu; không đọc dữ liệu đăng nhập.
- Hậu tố `- GHI CÔNG` trong tên tệp được bỏ qua khi nhận diện tên bài/nghệ sĩ và được lưu thành ghi chú nhắc kiểm tra. Bạn vẫn chủ động đặt trạng thái và nhập nguyên văn nội dung ghi công.
- Trạng thái do bạn nhập trong ứng dụng là dữ liệu quản lý chính.
