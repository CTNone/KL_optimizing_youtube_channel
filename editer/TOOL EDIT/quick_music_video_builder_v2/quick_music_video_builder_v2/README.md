# Quick Music Video Builder V2

V2 tiếp tục trực tiếp từ V1 và thêm 8 nhóm tính năng:

1. Duration 30m / 1H / 2H / 3H / Custom
2. Audio loudness normalization
3. Fade / Crossfade
4. Automatic chapter timestamps
5. Slow zoom / pan thumbnail
6. Snow / rain MP4 overlay
7. NVIDIA GPU encoder
8. Save / Load presets

Ngoài ra V2 sửa playlist preview: preview và render dùng cùng `Playlist seed`,
nên thứ tự bài + chapter timestamp sẽ khớp. Muốn random lại thì bấm `Shuffle random`.

---

## Cấu trúc project

    quick_music_video_builder_v2/
      app.py
      engine.py
      run.bat
      build.bat
      requirements.txt
      README.md
      V2_NOTES.md
      tools/
        ffmpeg.exe
        ffprobe.exe

V2 vẫn chỉ dùng Python standard library cho GUI/runtime.
FFmpeg làm toàn bộ media processing.

---

## 1. Cài Python

Khuyến nghị Windows 10/11 64-bit + Python 3.14.x.

Kiểm tra:

    py -3.14 --version

---

## 2. FFmpeg

Copy:

    ffmpeg.exe
    ffprobe.exe

vào:

    tools\

Nên dùng Windows FFmpeg build đầy đủ có:
- libx264
- AAC encoder
- FLAC encoder
- loudnorm
- acrossfade
- zoompan
- blend
- h264_nvenc nếu muốn NVIDIA

Lưu ý:
FFmpeg có thể liệt kê h264_nvenc nhưng GPU/driver vẫn có thể không chạy được.
V2 có nút `Test NVIDIA NVENC` và khi render NVIDIA sẽ encode thử 1 frame trước.

---

## 3. Chạy source

Double-click:

    run.bat

hoặc:

    py -3.14 -m venv .venv
    .venv\Scripts\activate
    python app.py

---

## 4. Duration

Có:

- 30 Minutes
- 1 Hour
- 2 Hours
- 3 Hours
- Custom

Custom cho phép 1–720 phút.

Vẫn giữ logic V1:
- 5 bài chỉ định đứng đầu mỗi vòng
- phần còn lại random
- hết toàn bộ danh sách mà chưa đủ duration → bắt đầu vòng tiếp theo
- video cuối cắt đúng target duration

---

## 5. Audio Loudness Normalization

Preset:
- -14 LUFS
- -16 LUFS
- -18 LUFS

V2 dùng FFmpeg `loudnorm`, sau đó đưa mọi nguồn về:

    48 kHz
    Stereo
    FLAC temporary

Điều này giúp thư viện trộn MP3/WAV/M4A/FLAC ổn định hơn V1.

Temporary FLAC chỉ tồn tại trong lúc render và tự xóa khi kết thúc.

---

## 6. Transition

### None
Track nối trực tiếp.

### Fade
Mỗi track fade in/out nhưng không overlap.

### Crossfade
Hai bài overlap theo số giây:
- 1
- 2
- 3
- 5

Crossfade làm timeline ngắn đi, nên app tính lại chapter timestamps theo điểm bài mới bắt đầu overlap.

---

## 7. Automatic Chapter Timestamps

Ví dụ output:

    christmas_mix.mp4

V2 tự tạo:

    christmas_mix_chapters.txt

Ví dụ:

    00:00 Christmas Love
    03:41 Winter Jazz
    07:52 Cozy December
    ...

Có thể copy vào YouTube description.

---

## 8. Thumbnail Motion

Có:

- Static
- Slow Zoom
- Pan Left-Right
- Pan Up-Down
- Cinematic Drift

Motion được thiết kế rất chậm để phù hợp music channel.
Ảnh được overscale trước rồi crop nên không kéo méo thumbnail.

---

## 9. Snow / Rain MP4 Overlay

Chọn overlay MP4 bất kỳ.

Mode:

### Screen
Dành cho overlay:
- snow nền đen
- rain nền đen
- particles
- dust/light particles

### Alpha
Dùng khi file overlay thật sự có alpha channel.

Opacity:
0.05 → 1.0

Overlay được loop tự động cho toàn duration.

---

## 10. NVIDIA NVENC

Output vẫn H.264.

CPU:

    libx264
    preset veryfast
    CRF 19

NVIDIA:

    h264_nvenc
    preset p5
    CQ 19

Trước render NVIDIA, V2 encode thử 1 frame.
Nếu không khởi tạo được h264_nvenc, app dừng ngay và báo lỗi.

---

## 11. Save / Load Presets

Preset JSON lưu:

- duration
- normalization on/off + target
- fade/crossfade mode + seconds
- visual motion
- overlay path/mode/opacity
- encoder
- playlist seed

Không lưu:
- thumbnail
- folder nhạc
- output MP4

Ví dụ bạn có thể tạo:

    christmas_cozy.json
    afro_house.json
    latin_rain.json

---

## 12. Playlist seed

Ví dụ:

    381742

Cùng:
- folder nhạc
- 5 bài đầu
- duration
- transition
- seed

→ thứ tự random sẽ lặp lại chính xác.

Bấm:

    Shuffle random

để tạo seed mới.

---

## 13. Đóng gói EXE

Đặt ffmpeg.exe + ffprobe.exe vào tools rồi double-click:

    build.bat

Kết quả:

    dist\QuickMusicVideoBuilderV2.exe

Máy chạy EXE cuối không cần cài Python.

---

## 14. Output

Video:

    MP4
    2560×1440
    30 fps
    H.264

Audio:

    AAC
    320 kbps
    48 kHz
    stereo

Sau render app tự verify:
- duration
- resolution
- video stream
- audio stream

---

## 15. Lưu ý về temp disk

V2 xử lý từng source audio thành temporary FLAC 48 kHz.
Nếu folder nhạc rất lớn, cần đủ dung lượng ổ đĩa tạm.

Chỉ những bài thực sự xuất hiện trong timeline target mới được preprocess.
File temp tự xóa sau khi render hoặc khi app kết thúc render.

---

## 16. Workflow gợi ý

    Thumbnail
        +
    Folder Music
        ↓
    5 fixed tracks
        ↓
    Random rest / loop
        ↓
    Loudness normalize
        ↓
    Fade / Crossfade
        ↓
    Chapter timestamps
        ↓
    Slow visual motion
        +
    Snow / Rain overlay
        ↓
    CPU / NVIDIA encode
        ↓
    1440p MP4
        +
    chapters.txt
