# Trình tự Thumbnail và các lỗi đã gặp

## Chuỗi thao tác

1. Khóa một lượt hoạt động, giữ đúng hồ sơ/tab/dự án. F5, đợi load, thêm 2 giây; không chạy hai luồng đồng thời.
2. Mở bảng cài đặt gần composer. Tìm nhóm Hình ảnh/Video ở bảng này, tránh các nhãn tương tự trên sidebar.
3. Chọn Hình ảnh và xác nhận ARIA/trạng thái chọn. Màu focus viền xanh không phải trạng thái chọn. Với fallback màu nền, dùng logic `VideoControls.selected` hiện có; hai màu khác nhau đơn thuần chưa đủ.
4. Chọn chính xác model Desktop bằng Playwright; đợi menu xuất hiện. Đọc lại model sau khi đóng dropdown. Mở bảng cài đặt để bước tỉ lệ/số ảnh không phải đua với animation đóng/mở.
5. `FlowSettings.applyRatio` và `apply` xác nhận tỉ lệ và số ảnh. Các lựa chọn đã gặp: 16:9, 4:3, 1:1, 3:4, 9:16; x1–x4. Xác minh lại khi Flow thay UI. Đóng menu, đợi ổn định.
6. Nếu có reference: snapshot ảnh cũ trước upload, mở picker cạnh prompt, tải đúng file, chờ xử lý xong. Chọn ảnh mới nhất thuộc lần upload này, bấm “Thêm vào câu lệnh”, xác nhận thumbnail mới trong composer.
7. Nhập đầy đủ prompt; tìm nút gửi đang bật. Gửi một lần và xác nhận Flow nhận lệnh qua trạng thái composer/nút gửi. Sau đó mới chờ kết quả.
8. Snapshot ảnh trước gửi gồm ảnh cũ và reference. Poll kết quả mới, yêu cầu ảnh đã load, loại composer/dialog/ảnh cũ. Gộp asset theo `data-asset-id`, `data-media-id`, `data-image-id` hoặc URL canonical. Khi số ảnh đúng và ổn định mới tải; không cộng dồn mọi URL tạm thời.
9. Mở từng ảnh mới, xác minh identity của bản xem. Tìm Download, chọn 2K miễn phí, arm capture trước bấm. Kiểm tra MIME, kích thước thật (cạnh lớn nhất >=2048) và hash. Lưu gốc và crop.
10. Escape/cleanup về composer; giữ kết quả tải thành công nếu cleanup có cảnh báo. Ghi status và đường dẫn file rõ ràng.

## Upload reference

`_attach_reference` theo dõi request upload/xử lý và MutationObserver nguồn ảnh mới. Chờ hết pending upload, không còn busy/progress và khoảng yên ổn trước chọn ảnh. Luồng đã dùng giới hạn chờ tới 5 phút và thêm khoảng yên 2 giây; kiểm tra giá trị hiện tại trước thay đổi.

Tên file chỉ là một tín hiệu: Flow có thể đổi tên hoặc dùng thumbnail URL khác. Không buộc filename phải xuất hiện trong mọi node. Không chọn ảnh cũ chỉ vì trùng vị trí. Selector token/handle được giải lại khi DOM remount; tránh `locator('img').nth(15)` giữ nguyên suốt quá trình upload.

Xác nhận reference qua ảnh mới được thêm vào composer và không còn ảnh cũ, không dùng so pixel toàn ảnh với thumbnail bị crop vì từng gây false negative. Nếu chưa xác nhận được, dừng trước gửi và ghi `reference_unverified`.

## Mở và tải ảnh

`FlowClicks.owner` có thể tìm wrapper nhiều lớp nhưng vẫn giới hạn một ảnh và kích thước thẻ; không cho phép click xuyên overlay/hộp thoại ngoài thẻ hoặc toolbar khác.

`FlowDownloads.save` giải lại ảnh theo identity nếu phần tử cũ bị thay. URL thumbnail có thể đổi size; dùng `identity` hiện có thay vì so URL nguyên chuỗi. Bản xem không nhất thiết lớn hơn thẻ lưới: từng có ảnh preview đúng nhưng bị loại vì yêu cầu `width > originalWidth * 1.2`. Hiện mã so identity và chờ nút Download, không coi kích thước hiển thị là bằng chứng model/kết quả đúng.

Giữ `verified2k` hoặc `pendingDownload` để retry ghi file mà không tải/upscale lần hai. Nếu đã bấm tải và kết quả không chắc chắn, không bấm lại để tạo file trùng. Các log mới phân biệt mở ảnh, xác nhận bản xem, chờ file 2K.

## Crop

`Files.crop_image`: `unit = min(width // 16, height // 9)`, kích thước `16*unit × 9*unit`; neo phía trên và canh giữa theo chiều ngang. Bản crop JPEG hậu tố `_16x9.jpg`, chất lượng 95. Nguồn 4:3 sẽ bỏ khoảng 25% chiều cao dưới; làm tròn pixel có thể thêm một lượng cắt nhỏ. Không cắt cố định 25% cho mọi tỉ lệ. Không ghi đè bản gốc.

## Chẩn đoán theo lỗi

| Hiện tượng | Điểm kiểm tra |
|---|---|
| Nút model sáng, không mở/chọn | Focus vs selected; pointer events; trigger/option là hai lớp; app chưa restart hoặc đang chạy controller cũ |
| “Menu mô hình chưa sẵn sàng” | Trigger đúng bảng; đợi DOM mới; tránh nhầm nút tóm tắt `Nano… x1` làm trigger thứ hai |
| Chọn đúng model nhưng không upload | Lượt mới nhất có thể là `settings_failed` ở tỉ lệ/số ảnh; xem reason trước sửa uploader |
| Không thấy tỉ lệ | Menu vừa bị đóng sau model; tránh close/reopen liên tục; kiểm tra label bỏ icon và bảng đã sẵn sàng |
| Timeout `nth(img)` | Picker remount / danh sách thay đổi khi upload; giải lại bằng token + ảnh mới |
| Chọn ảnh cũ | Snapshot không đủ, chọn quá sớm, hoặc UI còn reference cũ; không dùng index đầu tiên |
| “Nhiều ảnh mới hơn dự kiến” | URL placeholder đổi, duplicate rendition, reference bị tính là output; gộp asset và đợi ổn định |
| “Ảnh đang mở chưa khớp” | Identity, DOM ảnh cũ, canvas/preview UI mới; lỗi không chứng minh generation thất bại |
| `Failed to fetch` khi tải | Browser CORS; dùng capture download/file địa phương, không fetch thumbnail làm đường lui |
| Chỉ “Lượt Desktop đã kết thúc” | Đây là trạng thái kết thúc chung, không chứng minh thành công; đọc attempts/status/files |
| Video không thấy Veo dù bảng mở | Bảng có thể đang chọn Omni 1.1 Flash; trigger không được giả định tên hiện tại là Veo |

## Những điểm dùng chung với Video

Mã giao diện hiện hỗ trợ model dropdown đang chọn Omni để chuyển sang Veo. Token cho nút mở và option phải khác nhau; dùng lại token từng làm `locator.click` khớp cả hai phần tử. Thay đổi helper `VideoControls` có thể ảnh hưởng Thumbnail; chỉ sửa phạm vi liên quan và chạy kiểm thử chuyển chế độ.

Tên model đã gặp: Nano Banana Pro, Nano Banana 2.1, Nano Banana 2 Lite. Mã có alias Nano Banana 2 → 2.1, Nano Banana Lite → 2 Lite. Đây là lịch sử tương thích, không bảo đảm danh sách hiện hành của Google. Nếu tên mới xuất hiện, kiểm tra menu và cập nhật nhận diện có chủ đích.
