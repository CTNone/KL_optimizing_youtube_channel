# Tool Edit

Tool Edit là giao diện tạo video nền dài, kết nối trực tiếp với playlist trong Content Hub và thư viện nhạc của Music Manager.

## Bắt đầu

Chạy `run.bat` hoặc mở `editer/Chay_Editor.bat`. Trên màn hình đầu tiên, chọn một kiểu nguồn:

- **Ảnh nền loop** — dùng một ảnh làm nền, có thể thêm chuyển động chậm hoặc overlay.
- **Video Loop** — lặp các clip cùng bối cảnh để tạo nền dài liền mạch.
- **Ghép footage** — ghép nhiều clip khác nhau theo thứ tự đã chọn.

Sau đó chọn playlist nhạc và bộ lọc, đặt thời lượng / chất lượng xuất rồi bắt đầu render. Video xuất theo tỉ lệ **16:9**, chọn 720p, 1080p hoặc 2K (2560×1440). Định dạng là MP4.

## Chọn nhạc

Playlist được lấy từ `CONTENT HUB/data/content_hub.sqlite3`. Chọn kênh để xem kho nhạc đã gán cho kênh đó; có thể lọc thêm theo tên bài, nghệ sĩ, thể loại, nhạc cụ, có lời/không lời, không khí và trạng thái kiểm tra. Mặc định chỉ hiện bài **Đã kiểm tra**. Có thể mở Music Manager ngay trong Editor để cập nhật playlist hoặc phân loại nhạc, rồi bấm làm mới.

Nhãn thể loại, nhạc cụ, lời và không khí được lưu trong bảng bổ sung của cơ sở dữ liệu Music Manager; không sửa hay di chuyển file nhạc. Khi chưa có nhãn, các bộ lọc tương ứng sẽ không loại bỏ bài nào.

## Dự án, preset và kết quả

- **Lưu dự án / Mở dự án** lưu lại lựa chọn nguồn, playlist, thiết lập và đường dẫn xuất trong tệp JSON.
- Preset được lưu trong thư mục `presets/`.
- Kết quả mặc định nằm tại `editer/TOOL Video Flow OUTPUT/Editor`, cùng vị trí mà Editor cũ đã dùng.
- Content Hub, Music Manager, thư viện, preset và các video đã xuất được giữ lại.

## Yêu cầu chạy

Chạy source bằng Python có Tkinter. FFmpeg và FFprobe cần nằm trong `tools/` hoặc có thể được tìm thấy trong môi trường chạy. Để tạo bản Windows độc lập, đặt `ffmpeg.exe` và `ffprobe.exe` trong `tools/`, rồi chạy `build.bat`. Script chỉ thay `dist/ToolEdit` sau khi bản đóng gói mới vượt qua tự kiểm tra.

Tự kiểm tra giao diện (không render video):

```bat
py app.py --self-check "%TEMP%\tool_edit_check.json"
```

