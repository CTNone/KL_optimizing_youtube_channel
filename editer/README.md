# Editor workspace

## Thư mục và vai trò

- `TOOL EDIT/v3/v3/`: mã nguồn Editor, Flow Loop engine, hướng dẫn, preset và test. Chạy bản source bằng `run.bat`; build Windows EXE bằng `build_flow.bat` sau khi xác nhận FFmpeg/build dependencies sẵn sàng.
- `Nhạc jazz/`: thư viện audio, workbook YouTube Audio Library, công cụ quản lý nhạc và dữ liệu attribution. Các gói CapCut cùng báo cáo thư viện được xuất vào `TOOL Video Flow OUTPUT/Music Manager` và `TOOL Video Flow OUTPUT/Music Library`. Không xóa bài từ workbook/audit bằng suy đoán thể loại.
- `SOUND EFFECT/`: hiệu ứng âm thanh ambience dùng khi dựng.
- `TOOL Video Flow OUTPUT/`: kho chung cho sản phẩm của các tool; video ở `Video/`, ảnh ở `Thumbnail/`, bản dựng Editor ở `Editor/`.

## Quy trình đề xuất

1. Mở Editor từ source hoặc bản build mới nhất.
2. Trong tab **Flow Loop**, chọn ngày ở `Video Flow theo ngày` rồi bấm `Nạp ngày này`. Clip được nạp theo thứ tự thư mục/lượt; bỏ clip lỗi hoặc cảnh khác nhau trước khi xuất.
3. Chọn 1–3 giờ, preview ít nhất ba vòng, kiểm tra điểm cuối → đầu và bật/tắt playlist nhạc tùy kênh.
4. Xuất thành phẩm vào thư mục riêng theo kênh/ngày. Giữ clip nguồn Flow nguyên vẹn để có thể dựng lại.
5. Duyệt nhạc trong `Nhạc jazz/YouTube_Library_Review_3_Channels.xlsx`; trạng thái `Chờ nghe` cần được xác nhận bằng playback trước khi dùng.

## Nguyên tắc phân loại nhạc

- **HEARTHLUNE:** jazz cafe nhẹ, piano/acoustic Noel, carol instrumental, ambience lò sưởi.
- **SYLVANREST:** harp/flute/acoustic/Celtic nhẹ, piano nền và ambience thiên nhiên; tránh beat dồn.
- **ASTRALOOM:** drone/ambient/white-noise/brown-noise. Nhạc có beat hoặc giai điệu rõ cần đánh dấu loại sau khi nghe.

Workbook chỉ ghi nhận gợi ý từ pool/metadata hiện có. Tempo, mức năng lượng, vocal và quyền attribution cần kiểm tra lại trong YouTube Studio và bằng cách nghe file thực tế.
