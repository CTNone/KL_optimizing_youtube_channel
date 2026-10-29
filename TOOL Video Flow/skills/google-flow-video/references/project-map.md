# Bản đồ dự án

Gốc trên máy hiện tại: `C:\Users\CTN_Number_ONE\Documents\KHÓA LUẬN CỦA TÔI\TOOL Video Flow`. Kho output chung nằm trong workspace tại `TOOL Video Flow OUTPUT/`, gồm `Video/`, `Thumbnail/`, `NCTT/`, `Flow TXT/`, `Editor/`, `Music Manager/`, `Music Library/` và `Content Hub/`. Nếu chuyển máy, xác định lại workspace; không chép đường dẫn người dùng này vào logic dùng chung.

| File / thư mục | Vai trò |
| --- | --- |
| `launcher.py`, `Start-Studio.ps1` | Khởi chạy Studio; launcher có log/lỗi và named mutex chống mở trùng. Kiểm tra target shortcut thực tế trước khi sửa khởi chạy. |
| `studio_app.py` | GUI bốn tab; import `StudioFlow as DesktopFlow` từ `video_flow.py`; chọn ảnh, prompt, setting, profile và nơi lưu. |
| `video_flow.py` | `StudioFlow(DesktopFlow)`: chọn chế độ, setting, upload/gửi/theo dõi/tải/phục hồi/dừng. |
| `video_controls.js` | `mode`, `find`, `trigger`, `models`, `send`, `results`, `snapshot`, `openClip`, `downloadControl`, `resolutions`, `videoIdentity`. |
| `video_storage.py`, `video_metadata.py` | JSON nguyên tử; header/bytes/SHA-256; đọc track MP4 để biết width/height/duration. |
| `history_view.py` | Lịch sử theo ngày/giờ; `dated_output`, `register_video_folder`; chọn lượt tải lại. |
| `video-settings.json`, `video-runs.json` | Setting Desktop/nơi lưu và chỉ mục lượt trong kho output đặt bên ngoài repository. |
| `thumbnail-models.js`, `thumbnail-settings.js` | Bản điều chỉnh cục bộ cho Thumbnail, được inject sau runtime nguồn; thay đổi inject/controller có thể ảnh hưởng cả hai tab. |
| `../TOOL THUMBNAIL/desktop_flow.py` | Lớp nền: Chrome/CDP, runtime bridge, `flow_page`, `attach_reference`, disconnect. |
| `../TOOL THUMBNAIL/chrome-extension/` | `FlowErrors`, `FlowModels`, `FlowSettings`, `FlowDownloads`, clicks/content; cần giữ thư mục nguồn cạnh dự án. |

`StudioFlow.inject` nạp runtime nền rồi các helper cục bộ. `request(resumeRun)` là Thumbnail, chọn image trước khi chuyển cho runtime ảnh; `start_video` là luồng video riêng. Không thêm một lệnh luôn chọn Hình ảnh vào inject dùng chung.

Các helper/test có thể cần thêm thư mục TOOL THUMBNAIL vào sys.path. Không sửa một bản extension rồi giả định Desktop đã dùng nó: đọc import và thứ tự inject hiện tại.

## Dữ liệu mỗi lượt

`<nơi lưu>/Video/YYYY-MM-DD/HH-MM-SS_id/` chứa ảnh đầu vào, `video.json`, MP4 và sidecar. Giờ sản phẩm là UTC+7 (Asia/Saigon).

Các trường quan trọng của `video.json`: prompt/image/model/mode/ratio/count; time/updatedAt; status/stage; submitAttempted/submitted/submissionUncertain; baselineKeys/resultSources; files/resolutions/downloads; error/errorType/traceback/warnings.

Stage đang dùng: prepare → settings → upload → preflight → submit → wait → download → complete. submitted phản ánh click đã hoàn thành; việc Flow nhận lệnh còn được kiểm tra qua prompt trống/nút gửi disabled. Đọc lỗi và stage, không suy đoán từ submitted đơn lẻ.

File `preview-XX.json` lưu nguồn chuẩn hóa và URL bản xem đã xác nhận. `download-intent-XX.json` ghi yêu cầu tải đang dở. File tải có tên gắn index và hash nguồn; `.mp4.json` lưu source/resolution và metadata. Không thay nguồn hoặc preview URL bằng một clip cùng prompt chưa xác định được.
