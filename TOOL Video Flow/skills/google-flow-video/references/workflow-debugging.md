# Luồng và xử lý lỗi

## Tạo video

1. `start_video` khóa lượt chạy; reload dự án, đợi DOM và thêm 2 giây, inject runtime. Đây là chờ đầu lượt, khác với nhận hoàn tất.
2. `select_generation_mode(video)` tìm cặp Hình ảnh/Video trong bảng setting, tránh nút trùng tên ở sidebar. Xác nhận ARIA hoặc màu sáng hơn trong đúng nhóm; đã đúng thì không cần bấm lại. Tìm lại phần tử sau click vì menu có thể dựng lại/đóng.
3. `configure_video`: Video → Thành phần/Khung hình → ratio → model Veo → số lượng. Chờ danh sách model riêng; tách tên khỏi mô tả/credit, hỗ trợ dấu -, – và —. Không đòi full text dòng bằng đúng tên model.
4. `attach_reference` dùng lớp Thumbnail; đợi upload và xác nhận đúng ảnh mới. Điền prompt, snapshot tất cả nguồn và thumbnail trước gửi.
5. `FlowErrors.watch` nhận object `{visible, prompt, ignoreExisting:true}`. Truyền chuỗi gây lỗi `visible is not a function`. Ghi submitAttempted trước click, gửi một lần, xác nhận nhận lệnh; không tự retry khi chưa rõ.
6. `wait_for_videos` kiểm tra mỗi 0,25 giây; đủ count mới thì chuyển tải ngay, timeout hiện tại 1200 giây. Nó còn chờ đủ cả batch x2–x4; không mô tả thành tải từng clip ngay khi riêng clip đó xong nếu chưa thay thiết kế.

## Nhận hoàn tất

Flow thật dùng `flow-grid-tile-container`, `flow-video-tile`, `img.thumbnail` và `.footer-title`. Player có thể hidden, readyState=0, duration=NaN hoặc chưa tồn tại. Thumbnail hoàn chỉnh có naturalWidth>0 trong tile video có thể là kết quả; không yêu cầu hover/phát mới nhận diện.

Loại tile đang generating/loading/aria-busy hoặc progressbar chưa đạt max. `.progress-bar` của player là tiến độ phát, không phải generate. Không dựa vào một chữ “100%” ở nơi bất kỳ trên trang.

Snapshot gồm video ẩn và poster identity trước submit. Grid ảo có thể mount clip cũ sau submit; loại baselineKeys/posterKey và đối chiếu prompt đúng hàng. Prompt giống nhau không tự chứng minh đó là clip mới. Chuẩn hóa identity bỏ token/chữ ký hết hạn; playback có thể chuyển sang URL proxy `/asb/` sau hover. `data-video-source` và bản xem đã xác nhận giúp giữ đúng clip.

## Tải và trở về

- `openClip` chọn đúng thumbnail/tile theo source/poster. Flow thật có thể chuyển sang `/project/.../edit/<scene>` và dùng canvas, không có visible video/dialog. Sau navigation inject lại helper JS.
- Lưu preview-XX.json khi đã mở đúng clip. Khi phục hồi, kiểm tra nguồn và URL thuộc đúng dự án trước dùng lại; không invent scene ID.
- Nút tải thật có thể mang aria-label “Tải nội dung nghe nhìn xuống”, ligature `download`, `file_download`, `download_2`; nút khác có thể ẩn. Giữ token thumbnail và token nút tải riêng để tránh strict-mode 2 phần tử.
- Menu Angular: `.cdk-overlay-pane [role=menu]`, `flow-menu-item > button[role=menuitem]`, `.label` và caption. Đọc nhãn độ phân giải riêng vì textContent có thể ghép `720pKích...`.
- Loại disabled/aria-disabled/lock/nâng cấp trong **chính dòng lựa chọn**. Không quét container chung có mục 4K khóa rồi loại cả 1080p. Loại GIF; xếp resolution theo pixel, chọn duy nhất mức cao nhất được phép.
- Bấm tải một lần với `expect_download`, tối đa 900000 ms; báo tiến độ mỗi 5 giây khi chuẩn bị/upscale. Thời gian chuẩn bị file cao hơn độ phân giải gốc không có nghĩa generate chưa xong. Hủy phải dọn tác vụ chờ download con.
- Lưu `.part`, kiểm tra header/hash/metadata rồi rename. Lỗi ghi file thử lưu lại chính Download artifact, không click lại/generate lại. Ghi file theo index để tải một phần không lệch kết quả; cache kiểm tra source/hash.
- Edit route cần quay về URL dự án; Escape không đủ. Với overlay, đóng menu/preview rồi xác nhận và focus composer. Nếu không xác nhận được, lưu warning.

## Phục hồi

`download_existing_record`/`retry_video_download` dùng lượt đang chọn hoặc lượt đã gửi chưa tải đủ; không mở hộp folder để giả làm tải lại. Nơi lưu là nút riêng. Không upload/reload/gửi lại để chữa tải lỗi. Ưu tiên resultSources và preview đã xác nhận; legacy thiếu sources chỉ tải khi đúng prompt/count xác định duy nhất. Nếu mơ hồ, giữ lỗi và yêu cầu đúng clip/dự án, không chọn đầu tiên.

## Chẩn đoán

Lấy video.json mới nhất từ video-runs.json hoặc nơi lưu Desktop, xem stage đầu tiên lỗi, traceback, cờ gửi, count và nguồn. Ghi DOM của đúng clip/menu với selector, aria, disabled, route và nguồn thay vì thử regex rộng hoặc click tọa độ tùy ý. Log có thể chứa URL ký; không đưa dữ liệu phiên/cookie vào skill hoặc báo cáo công khai.

README có các đoạn lịch sử đã lỗi thời (chờ ổn định 8/2 giây, chưa test thật). Dùng mã hiện tại, AUDIT.md và bằng chứng trong validation để xác định trạng thái.
