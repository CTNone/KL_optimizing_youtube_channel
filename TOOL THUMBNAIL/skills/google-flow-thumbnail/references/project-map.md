# Kiến trúc và vị trí mã

Bàn giao ngày 2026-10-12. Các đường dẫn dưới đây là vị trí trên máy người dùng; kiểm tra chúng còn tồn tại ở phiên mới. Không mang cookie, token, hồ sơ Chrome hay lịch sử prompt vào gói skill.

## Thư mục

```text
C:\Users\CTN_Number_ONE\Documents\KHÓA LUẬN CỦA TÔI\
  TOOL THUMBNAIL\   mã gốc Desktop và extension dùng chung
  TOOL Video Flow\  phần mềm tích hợp đang được shortcut sử dụng
  TOOL NCTT\        nghiên cứu thị trường, thư viện thumbnails\
```

Shortcut `NCTT + Thumbnail.lnk` được kiểm tra trong phiên trước: chạy `pythonw.exe` với `TOOL Video Flow\launcher.py`. Kiểm tra lại shortcut nếu nghi người dùng đang chạy bản khác.

`launcher.py` dùng mutex chống mở nhiều instance. `studio_app.py` thêm TOOL THUMBNAIL vào `sys.path`, rồi import `StudioFlow` từ `video_flow.py` dưới tên `DesktopFlow`. `integrated_app.py` trong TOOL THUMBNAIL là app cũ dùng controller gốc, không phải lớp tích hợp trên.

## Mã dùng chung trong TOOL THUMBNAIL

| File | Vai trò / điểm vào cần tìm |
|---|---|
| `desktop_flow.py` | Playwright Chrome; `connect_existing`, `start`, `inject`, `request`, `bridge`, `attach_reference`, `_attach_reference`, `capture_download` |
| `chrome_profile.py` | Quét hồ sơ Chrome và metadata; không in dữ liệu phiên đăng nhập |
| `chrome-extension/content.js` | `runSingle` / `runAttempt`, `clickControl`, `results`, gửi prompt, nhận kết quả, ghi lịch sử |
| `chrome-extension/flow-models.js` | Chọn mô hình của extension/controller gốc |
| `chrome-extension/flow-settings.js` | Tỉ lệ, số ảnh của extension/controller gốc |
| `chrome-extension/flow-clicks.js` | Owner/vùng bấm an toàn, hit testing, xử lý lớp phủ thẻ ảnh |
| `chrome-extension/flow-downloads.js` | Mở đúng ảnh, Download → 2K, kiểm tra file, đóng bản xem |
| `chrome-extension/flow-errors.js` | Theo dõi lỗi Flow; phân biệt lỗi hạn mức/generation |
| `chrome-extension/native-host/host.py` | `Files.inspect_image`, `import_image`, `crop_image`, lưu file và chống trùng hash |

`DesktopFlow.inject` nạp runtime và các JS dùng chung vào tab. Desktop giả lập cầu `chrome.runtime.sendMessage` bằng binding Playwright; không cần extension được cài để chạy Desktop.

## Lớp ghi đè trong TOOL Video Flow

| File | Vai trò |
|---|---|
| `video_flow.py` | `StudioFlow(DesktopFlow)`; ghi đè `inject` và `request`; `select_generation_mode`, `open_video_settings`, `select_thumbnail_model` |
| `video_controls.js` | Đọc label bỏ icon, tìm bảng cài đặt, `mode`, `modeGroup`, `settingsRoot`, `trigger`, `find`, `models` |
| `thumbnail-models.js` | Ghi đè `globalThis.FlowModels`; ưu tiên nút trong bảng cài đặt đang mở |
| `thumbnail-settings.js` | Ghi đè `globalThis.FlowSettings`; áp dụng tỉ lệ/số ảnh |
| `studio_app.py` | GUI tích hợp, tạo controller và các tab |
| `history_view.py` | Lịch sử tích hợp, đọc kết quả Thumbnail và Video |

`StudioFlow.inject` nạp các ghi đè SAU mã chung. Thay đổi `flow-models.js` hoặc `flow-settings.js` gốc có thể bị ghi đè hoàn toàn. Ngược lại, `flow-downloads.js`, `flow-clicks.js`, `content.js` chung vẫn được Desktop tích hợp sử dụng.

`StudioFlow.request(type='resumeRun')` hiện thực hiện: chọn Hình ảnh → chọn model Desktop bằng Playwright → mở lại bảng cài đặt đã xác minh → chuyển vào luồng JS chung. `select_thumbnail_model` dùng binding `__studioModelPress` / `__studioModelDismiss`; bấm cả trigger và option bằng `locator.click`, xác nhận model qua `FlowModels.chooseBest` trước khi tiếp tục.

## Dữ liệu và kết nối

- State theo hồ sơ Desktop ở `TOOL THUMBNAIL\desktop-data\<profile>\state.json`: `history`, `limits`. Profile kết nối Chrome thường có dạng `chrome-<hash>`; đừng cố định hash của một tài khoản.
- Lịch sử có `attempts[].time`, `model`, `status`, `reason`, `files`; đọc lượt mới nhất để tránh chữa lại lỗi cũ.
- Video có `TOOL Video Flow OUTPUT\Video\<ngày>\<lượt>\video.json`. `submitted`, `submitAttempted`, `stage`, `error` giúp phân biệt lỗi trước/sau gửi. Chỉ đọc khi liên quan giao diện dùng chung.
- `connect_existing` đọc `DevToolsActivePort` của Chrome User Data và kết nối CDP localhost. Trên Chrome có hỗ trợ, người dùng bật remote debugging và chấp thuận kết nối. Giữ browser hiện có khi tool disconnect.
- Mất kết nối CDP không chứng minh selector sai. Không tự clone session hay mở một hồ sơ mới để thay cho tab đăng nhập sẵn của người dùng.
- `mode-review/`, `*-review.py`, và `inspect_flow_controls.py` là file kiểm thử/đối chiếu của các phiên sửa trước; không coi chúng là mã đang chạy.
