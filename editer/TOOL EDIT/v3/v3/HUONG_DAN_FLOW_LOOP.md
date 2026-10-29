# Editor nâng cấp: Google Flow → video loop dài

## Chạy

Mở `dist/ToolEdit/ToolEdit.exe`. Giữ nguyên thư mục `_internal` bên cạnh EXE;
không copy riêng EXE. Bản này kèm Python, Tk, FFmpeg và FFprobe.
Chạy source bằng `run.bat` cũng được. Đóng gói lại bằng `build_flow.bat`.

## Quy trình

1. Chọn ảnh tham chiếu tại mục **Thumbnail** nếu muốn lưu ảnh cùng dự án.
2. Trong tab **Flow Loop**, chọn thể loại và cường độ; nhập thêm yêu cầu chuyển động
   bằng tiếng Anh nếu cần. Bấm **Tạo prompt và sao chép**.
3. Dùng ảnh + prompt trong tool Google Flow đang có. Tải clip hoàn tất về máy.
4. Bấm **Thêm clip**. Dùng một clip tốt hoặc nhiều clip từ cùng ảnh/cùng cảnh.
   Chọn một clip rồi dùng ↑/↓ để đổi thứ tự; chọn nhiều clip để xóa.
5. Mặc định hòa trộn **0.8 giây**. Có thể thử 0.5–1.2 giây.
   Cắt đầu/cuối áp dụng cho từng clip; clip sau cắt phải dài hơn hai lần hòa trộn.
6. Bấm **Tạo và mở preview 3 vòng**. Xem cả các điểm nối giữa clip và khi vòng cuối
   quay lại vòng đầu. Preview không có âm thanh, tập trung kiểm tra hình ảnh.
7. Trong **Audio & Playlist**, chọn **1 Hour** hoặc thời lượng khác.
   Bật **Ghép playlist nhạc** ở Flow Loop nếu cần nhạc: chọn folder, chọn đủ 5 bài đầu,
   rồi dùng normalization/crossfade audio như trước. Tắt để xuất video không tiếng.
8. Trong **Output & Presets**, chọn độ phân giải và encoder. CPU dùng được khi
   Quick Sync/NVIDIA không hoạt động. Chọn đường dẫn Output MP4 rồi bấm **TẠO VIDEO**.

**Lưu dự án / Mở dự án** lưu ảnh, clip và thứ tự, folder nhạc, 5 bài đầu, seed,
prompt settings, thời lượng, output và các cấu hình edit. JSON tham chiếu file gốc;
không đóng gói các file media. Di chuyển media thì cần chọn lại đường dẫn.
Preset cũ vẫn mở được và mặc định dùng chế độ Thumbnail.

## Cách xử lý hình ảnh

Clip được chuẩn hóa về 30 fps, độ phân giải đầu ra, SAR 1 và H.264/yuv420p.
Nguồn không phải 16:9 được thêm viền để giữ toàn bộ bố cục.
Không áp dụng zoom/pan hoặc overlay của tab Visual trong chế độ Flow Loop.
Âm thanh gốc của clip Flow được bỏ.

Mỗi clip đóng góp phần thân và phần hòa trộn đuôi sang đầu clip tiếp theo.
Clip cuối hòa trộn về clip đầu. Với một clip, đuôi hòa trộn về chính đầu của nó.
Không đảo chiều tuyết/mưa. Với một clip 8 giây và overlap 0.8 giây, mỗi vòng dài
7.2 giây; số khung hình được tính theo 30 fps.

Engine xử lý từng cặp clip trên đĩa để hạn chế RAM, tạo loop master rồi lặp bằng
stream copy. Chỉ mã hóa phần loop, không mã hóa lại từng giờ hình ảnh.
CPU dùng CRF 23 cho 720p, CRF 20 cho 1080p/1440p; giới hạn bitrate lần lượt
4/8/16 Mbps. Kích thước thành phẩm phụ thuộc độ phức tạp của cảnh và encoder.

Crossfade không sửa được camera trôi, vật thể biến dạng hoặc cảnh thay đổi lớn.
Nếu preview có bóng đôi, hãy bỏ clip lỗi, giảm chuyển động trong prompt hoặc tạo lại.
Không coi kiểm tra kỹ thuật là bảo đảm điểm nối vô hình; vẫn cần xem preview.

## Đầu ra

- `ten_video.mp4`: video dài, kiểm tra thời lượng, kích thước, âm thanh và số khung hình.
- `ten_video_preview.mp4`: preview ba vòng khi dùng nút preview.
- `ten_video_chapters.txt`: mốc bài hát khi bật nhạc.
- `ten_video_loop/loop_master.mp4`: đoạn loop nền để tái sử dụng.
- `ten_video_loop/render_report.json`: clip nguồn, số khung hình, cấu hình,
  prompt gợi ý và kết quả kiểm tra. Prompt gợi ý không xác nhận prompt đã dùng tạo clip.

Render ghi video vào file tạm, kiểm tra rồi mới thay output. Hủy/lỗi render không thay
video output đang có. Nút ghi đè hỏi trước khi thay video hoặc preview hiện có.

## Demo đã tạo

Trong `demo_flow/` có preview ba vòng, video 1 giờ 720p không tiếng,
`demo_project.json` để mở lại và báo cáo kiểm tra. Nguồn là một clip tuyết 8 giây
có sẵn trong kho Google Flow; không thay đổi clip gốc.

## Kiểm tra source

```
py selftest.py
py -m unittest test_flow_loop -v
```

Kiểm thử tích hợp dùng FFmpeg thật: một/nhiều clip, nguồn 24/25 fps, Unicode và
đường dẫn có dấu cách, nhạc chuẩn hóa + crossfade + chapters, đúng số khung hình,
giải mã toàn bộ bản ngắn, preset cũ và hủy render bảo vệ output.
Demo một giờ được kiểm tra riêng; GPU cần test trên máy sử dụng.
