# V2 Notes / khác V1

## Pipeline V1

    Source tracks
      ↓
    concat
      ↓
    thumbnail + audio
      ↓
    libx264 output

## Pipeline V2

    Source tracks
      ↓
    ffprobe duration
      ↓
    build seeded playlist
      ↓
    preprocess used tracks
      - optional loudnorm
      - 48 kHz stereo
      - optional fade
      - temp FLAC
      ↓
    timeline audio
      - concat OR acrossfade
      ↓
    AAC 320k final audio
      ↓
    thumbnail motion
      +
    optional looping MP4 overlay
      ↓
    CPU libx264 OR NVIDIA h264_nvenc
      ↓
    final 1440p MP4
      ↓
    ffprobe verification

## Vì sao normalize từng source trước

Điều này giải quyết vấn đề V1 khi folder trộn:
- MP3
- WAV
- AAC/M4A
- FLAC
- sample rates khác nhau
- channel layouts khác nhau

Sau preprocessing, timeline dùng source audio đồng nhất.

## Single-pass loudnorm

V2 dùng dynamic single-pass loudnorm để giữ app đơn giản và thời gian xử lý hợp lý.
Nếu cần mastering chính xác hơn trong V3 có thể nâng cấp thành two-pass EBU R128 measurement + correction.

## Crossfade

V2 dùng FFmpeg acrossfade với linear triangular curves (`tri`).
Chapter của track mới bắt đầu tại đầu vùng crossfade.

## Overlay

Screen blend phù hợp nhất với snow/rain stock loop có nền đen.
Alpha mode chỉ nên dùng với overlay có alpha thật.

## Render speed

Visual motion (zoompan) và Screen blend vẫn có filter CPU.
NVENC tăng tốc encoder, nhưng không có nghĩa toàn bộ filter graph chạy trên GPU.
