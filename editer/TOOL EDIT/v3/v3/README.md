# Tool Edit

Tool Edit ghép nhạc nền và sound effect vào một video đã dựng sẵn. Video hình ảnh được giữ nguyên bằng cách sao chép luồng video; âm thanh được chuẩn hóa, ghép và mã hóa AAC.

## Quy trình

1. Chọn video đầu vào; bấm **Xem trước** để phát video ngay trên màn hình (bản xem trước tắt tiếng). Thời lượng xuất mặc định bằng video gốc; có thể rút ngắn bằng MM:SS hoặc HH:MM:SS, và không thể đặt dài hơn video gốc. Chọn thư mục nhạc từ Music Manager.
2. Nghe và chọn thủ công 3–5 bài mở đầu. Các bài còn lại được xáo trộn ngẫu nhiên; danh sách tiếp tục lặp cho đến hết video.
3. Tool tự cắt khoảng lặng ở đầu/cuối bài (ngưỡng -55 dB), chuẩn hóa từng bài tới -14 LUFS / -1.5 dBTP, rồi đặt đúng 1 giây im lặng giữa các bài. Ba giây cuối nhạc giảm dần.
4. Tùy chọn chọn kho sound effect. Mỗi lần phát chọn ngẫu nhiên một file, cách nhau ngẫu nhiên 1–5 phút. Nhấp đúp tên trong danh sách để đặt tên hiển thị; đường dẫn vẫn trỏ tới file gốc.
5. Mặc định Tool Edit bỏ tiếng gốc của video. Bật **Giữ âm thanh gốc** nếu muốn trộn nó ở mức nền cùng nhạc; khi tắt, đầu ra chỉ dùng nhạc và sound effect.
6. Chọn nơi lưu và bắt đầu ghép. Mặc định lưu trong `OUTPUT TỔNG/Editor`. Tool nhớ thư mục gần nhất riêng cho video, nhạc, sound effect và nơi lưu trong `tool_edit_settings.json`.

Trước khi báo hoàn tất, Tool Edit kiểm tra track âm thanh và mức âm trong 30 giây đầu. Nếu đoạn đầu gần như im lặng, Tool báo lỗi thay vì coi file đó là thành phẩm.

Tool cần FFmpeg và FFprobe trong `tools/` hoặc trên PATH. Cửa sổ source chạy bằng `py app.py`; tự kiểm tra giao diện (không render) bằng `py app.py --self-check "%TEMP%\tool_edit_check.json"`. Đóng gói Windows bằng `build_flow.bat`.
