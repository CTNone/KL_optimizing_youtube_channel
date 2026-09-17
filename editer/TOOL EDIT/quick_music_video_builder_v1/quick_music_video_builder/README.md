# Quick Music Video Builder

Ứng dụng Windows đơn giản để tạo bản dựng sơ bộ video nhạc:

- Input: 1 ảnh thumbnail
- Input: 1 folder nhạc
- Chọn cố định 5 bài đầu tiên
- Các bài còn lại được xáo trộn ngẫu nhiên
- Nếu chưa đủ 1 giờ, playlist bắt đầu vòng mới
- Mỗi vòng mới: 5 bài cố định vẫn đứng đầu, phần còn lại được xáo trộn lại
- Output: MP4 chính xác 01:00:00
- Video: 2560x1440, 30 fps, H.264
- Audio: AAC 320 kbps, stereo, 48 kHz
- Không kéo méo thumbnail: scale đầy khung rồi crop giữa
- App không sửa file nhạc gốc

## 1. Cài Python

Khuyến nghị Windows 10/11 64-bit + Python 3.14.x 64-bit.

Khi cài Python:
- bật "Add Python to PATH" nếu installer có tùy chọn đó
- cài Tcl/Tk (mặc định của bản python.org)

Kiểm tra trong Command Prompt:

    py --version
    py -3.14 --version

## 2. Chuẩn bị FFmpeg

Tải một Windows build của FFmpeg.

Trong package FFmpeg, tìm:
- ffmpeg.exe
- ffprobe.exe

Copy cả hai vào:

    quick_music_video_builder\tools\

Cấu trúc:

    quick_music_video_builder\
      app.py
      build.bat
      run.bat
      requirements.txt
      tools\
        ffmpeg.exe
        ffprobe.exe

Trong giai đoạn phát triển, app cũng có thể dùng FFmpeg trong PATH.
Khi build .exe, build.bat yêu cầu 2 file trong tools để nhúng vào app.

## 3. Chạy source

Cách nhanh:

    run.bat

Hoặc thủ công:

    py -3.14 -m venv .venv
    .venv\Scripts\activate
    python app.py

## 4. Cách sử dụng

1. Chọn ảnh thumbnail.
2. Chọn folder chứa nhạc.
3. App quét các định dạng:
   MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, WMA.
4. Chọn đủ 5 bài đầu.
5. Chọn nơi lưu .mp4.
6. Có thể bấm "Xem thứ tự playlist".
7. Bấm "TẠO VIDEO 1 GIỜ".

Ví dụ một vòng:

    Bài A
    Bài B
    Bài C
    Bài D
    Bài E
    Bài X
    Bài M
    Bài K
    Bài Y
    ...

A-E là 5 bài bạn cố định.
Các bài còn lại là random không lặp trong cùng vòng.

Nếu hết cả folder mà chưa đủ 1 giờ, app tạo vòng tiếp theo:

    A, B, C, D, E, [random phần còn lại lần nữa]

Video được cắt đúng ở 01:00:00.

## 5. Đóng gói EXE

Chỉ cần double-click:

    build.bat

Hoặc chạy từ Command Prompt.

Build script sẽ:
- tạo virtual environment nếu chưa có
- cài/cập nhật PyInstaller
- kiểm tra ffmpeg.exe và ffprobe.exe
- nhúng FFmpeg vào app
- build dạng one-file, không hiện cửa sổ console

Kết quả:

    dist\QuickMusicVideoBuilder.exe

Máy chạy file EXE cuối không cần cài Python.

## 6. Lưu ý codec

Bản v1 dùng FFmpeg concat demuxer để ưu tiên tốc độ.
Nó phù hợp nhất khi thư viện nhạc tương đối đồng nhất, ví dụ đa số MP3/M4A.

Nếu folder chứa nhiều codec rất khác nhau và FFmpeg báo lỗi concat,
bản tiếp theo nên thêm chế độ "Normalize audio trước khi ghép":
- convert từng track sang AAC 48 kHz stereo ở temp
- concat các file đã chuẩn hóa
- xóa temp khi xong

## 7. Nâng cấp nên làm tiếp

- Chọn thời lượng 30/60/120 phút
- Chọn 1080p / 1440p / 4K
- NVIDIA NVENC / Intel Quick Sync để render nhanh
- Fade audio giữa bài
- Giữ khoảng lặng 0.2–1 giây giữa bài
- Random seed để tái tạo đúng playlist
- Export playlist .txt / chapter timestamps
- Drag & drop thứ tự 5 bài đầu
- Lưu preset theo từng kênh YouTube
- Batch render nhiều thumbnail/folder
