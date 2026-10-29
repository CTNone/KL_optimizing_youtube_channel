# Quản lý nhạc và ghi công

Nhấp đúp **Mo_Quan_Ly_Nhac.cmd** trong thư mục Nhạc jazz. Ứng dụng dùng Python/Tkinter có sẵn trên máy, không cần Internet hay đăng nhập.

1. Tìm tên bài hoặc nghệ sĩ, lọc theo nhóm. Bài có nhiều bản sao ở các nhóm dùng chung một hồ sơ ghi công.
2. Chọn **+ Tạo kênh**, chọn kênh đó, rồi Ctrl/Shift chọn các bài và bấm **Gán bài đã chọn**. Mỗi kênh giữ playlist riêng; cột **Kênh** cho biết bài đã được gán ở đâu. Dùng bộ lọc **Trong kênh đang chọn** để xem playlist; **Bỏ khỏi kênh** chỉ bỏ phân loại, không xóa bài hay hồ sơ ghi công.
3. Chọn một bài, bấm **Nghe bài** để mở trình phát mặc định. Bạn tự kiểm tra giấy phép, chọn **Không cần ghi công** hoặc **Cần ghi công**, dán nguyên văn nội dung ghi công và lưu. Nguồn, tên giấy phép và ghi chú là các trường bạn tự nhập. Nghe nhạc không tự xác định được giấy phép; ứng dụng chỉ lưu kết quả kiểm tra của bạn.
4. Tạo dự án theo tên dự án CapCut. Ctrl/Shift để chọn khoảng 20 bài, bấm **Thêm bài đã chọn**. Bài đã thêm tự được đánh dấu bằng số dự án đã sử dụng trong cột Dự án. Có bộ lọc bài đã dùng/chưa dùng. Chọn bài trong danh sách dự án để sửa hồ sơ; dùng ↑/↓ để đổi thứ tự, Bỏ khỏi dự án để bỏ chọn.
5. **Xem / sao chép nội dung ghi công** tập hợp nguyên văn nội dung của những bài có trạng thái Cần ghi công. Bài Chưa kiểm tra luôn được báo riêng.
6. **Xuất nhạc + ghi công cho CapCut** tạo gói mới trong `TOOL Video Flow OUTPUT/Music Manager/CapCut_Exports`, có thư mục `Audio`, `GHI_CONG.txt`, `CAN_KIEM_TRA.txt`, danh sách CSV và bản chụp JSON. Trong CapCut, mở dự án > Media > Import, chọn các bài trong Audio. Số đầu tên tệp thể hiện thứ tự lựa chọn. Đây là gói tài nguyên để nhập vào mọi dự án CapCut, không tạo/sửa tệp dự án nội bộ của CapCut.

Kênh được lấy trực tiếp từ `CONTENT HUB/data/content_hub.sqlite3`; hãy tạo/sửa kênh trong Content Hub. Music Manager gán nhạc bằng ID kênh Hub và lưu playlist cùng database. Trong **Tool Edit**, tab **Audio & Playlist** chọn cùng tên kênh. Bấm **Làm mới playlist từ Music Manager** nếu vừa thay đổi danh sách khi Editor đang mở.

Gói hoàn chỉnh yêu cầu mọi bài đã được kiểm tra và bài cần ghi công có nội dung. Bạn có thể chủ động xuất bản nháp để dựng video khi chưa kiểm tra xong; bản nháp có danh sách cần xử lý. Bài thiếu tệp không thể xuất. Khi đăng video, dán nội dung GHI_CONG.txt vào mô tả theo yêu cầu của giấy phép bạn đã kiểm tra.

Các bài trùng giữa nhóm chỉ xuất một lần trong một dự án. Mỗi lần xuất tạo một thư mục mới, giữ nguyên gói cũ để truy vết. Nếu bạn đổi danh sách hoặc thông tin ghi công, hãy xuất lại và dùng gói mới. Nội dung ghi công trong gói cũ không tự cập nhật.

## Dữ liệu và sao lưu

- Thư viện nhạc nguồn hiện có không bị đổi tên hoặc di chuyển. Bài mới tải từ công cụ bổ sung được lưu trong TOOL Video Flow OUTPUT/Music Library/Tracks; Music Manager quét cả hai vị trí. Bài được sao chép khi xuất.
- Thư viện, ghi công và quan hệ bài–kênh nằm trong `CONTENT HUB/data/content_hub.sqlite3` cùng dự án Hub. Dữ liệu có sẵn trong `Music_Manager/data/music.sqlite3` được sao chép một lần khi mở Music Manager; database cũ được giữ nguyên làm bản nguồn.
- Sao lưu tự động khi mở ứng dụng; nút Sao lưu dữ liệu tạo thêm bản SQLite trong `TOOL Video Flow OUTPUT/Music Manager/Backups`.
- Để khôi phục: đóng ứng dụng, sao chép bản sao lưu mong muốn thành `data/music.sqlite3` (giữ bản hiện tại riêng trước).
- Quét lại thư viện sau khi thêm/xóa/di chuyển nhạc. Dữ liệu ghi công và dự án đã lưu được giữ lại. `.audio_cache` và các gói xuất không được quét thành nhạc nguồn.
- Nguồn metadata ban đầu là `TOOL Video Flow OUTPUT/Music Library/library_audit.json` đã đối chiếu Excel (có hỗ trợ đọc tệp audit cũ trong thư mục nhạc). Tệp nhạc mới được nhận dạng theo tên `Tên bài - Nghệ sĩ`; nếu thiếu nghệ sĩ, hiển thị Chưa xác định. Tên sai cần được sửa ở tệp nguồn rồi quét lại; hồ sơ của tên cũ vẫn giữ để tránh mất dữ liệu.
- Tất cả bài khởi đầu là **Chưa kiểm tra**. Không tự suy luận trạng thái từ tệp Excel, cookie hoặc nội dung tài liệu; không đọc dữ liệu đăng nhập.
- Hậu tố `- GHI CÔNG` trong tên tệp được bỏ qua khi nhận diện tên bài/nghệ sĩ và được lưu thành ghi chú nhắc kiểm tra. Bạn vẫn chủ động đặt trạng thái và nhập nguyên văn nội dung ghi công.
- Xuất danh mục CSV là bản sao để xem/lưu, không đồng bộ hai chiều với Excel. Trạng thái do bạn nhập trong ứng dụng là dữ liệu quản lý chính.
