# YouTube Content Hub — quản trị quy trình sản xuất đa kênh

Phiên bản MVP desktop, dành cho **một người quản lý nhiều kênh**. Đây là lớp quản trị
chung cho Studio NCTT + Thumbnail + Video và editor Flow Loop hiện có.

## Mở phần mềm

- Bản EXE: `dist/YouTubeContentHub/YouTubeContentHub.exe`.
- Bản source: chạy `run.bat` (Python 3.10+ có tkinter).
- Demo riêng: `run_demo.bat`, hoặc EXE với tham số `--demo`.
- Database sản xuất: `data/content_hub.sqlite3`; database demo: `data/demo.sqlite3`.
  Demo không được trộn vào dữ liệu sản xuất.
- Thư viện nhạc, ghi công và playlist theo kênh cũng dùng database sản xuất này.
  Music Manager lấy danh sách kênh từ Hub; nhạc cũ trong `editer/Nhạc jazz/Music_Manager/data/music.sqlite3`
  được nhập một lần khi mở database sản xuất và file nguồn được giữ nguyên.
- Handoff, render, bản backup và hồ sơ xuất được đặt trong `TOOL Video Flow OUTPUT/Content Hub/`.

Giữ CONTENT HUB cạnh TOOL Video Flow, TOOL THUMBNAIL, TOOL NCTT và editer trong
workspace. Giữ `_internal` cạnh EXE. Python không cần để chạy Hub đóng gói hoặc
render bằng engine kèm theo; Studio tạo nội dung hiện có vẫn dùng Python và các
phụ thuộc đã cài của Studio. Không có dịch vụ cloud mới hoặc API key mới trong Hub.

## Bắt đầu với dữ liệu thật

1. Ở bộ lọc **Tất cả kênh**, bấm **Kênh** để tạo kênh: tên, ngách, URL, phong cách.
   Chọn một kênh rồi bấm Kênh để sửa hoặc lưu trữ; lưu trữ không xóa dự án.
2. Bấm **+ Dự án nội dung**. Gán kênh, tiêu đề, brief, người phụ trách và hạn.
3. **Lưu brief** trước khi chuyển bước. Bấm **Chuyển bước tiếp** để bắt đầu nghiên cứu.
4. Trong **Tool & Render**, mở Studio hiện có. Nghiên cứu/tạo ảnh/clip bằng luồng đang
   sử dụng; Hub không tự submit prompt hoặc tiêu thụ lượt tạo nội dung.
5. Trong **Tài nguyên**, chọn loại rồi **Nhập file**. Nhập dữ liệu nghiên cứu, thumbnail,
   clip theo từng bước. File gốc được giữ tại chỗ; hệ thống ghi hash SHA-256.
6. Khi ở **Dựng video**, thêm clip và tùy chọn nhạc vào dự án. Bấm đưa vào hàng đợi.
   Thời lượng mặc định 60 phút, 720p, CPU, overlap 0.8 giây; bật nhạc cần ≥5 bài vì
   lấy playlist của kênh đang chọn (hoặc nhạc đã nhập riêng vào dự án). Render chạy một tác vụ tại một thời điểm.
   Hoặc mở editor để cấu hình nâng cao rồi nhập video thành phẩm về Hub.
7. Render thành công tự đăng ký file **Video thành phẩm / main**. Bấm Làm mới và chuyển
   sang **Kiểm duyệt**. Xem video/preview trong editor, xác nhận bốn mục QC rồi duyệt.
8. Ở **Sẵn sàng**, nhập lịch đăng tương lai `YYYY-MM-DD HH:MM` theo giờ Việt Nam, xác nhận.
9. Tự đăng/đặt lịch trong YouTube Studio. Khi đã đăng, nhập URL YouTube và xác nhận
   chuyển sang **Đã đăng**. Đây là xác nhận của người vận hành, không phải xác minh từ API.
10. Nhập snapshot hiệu suất từ YouTube Studio. Snapshot là số tích lũy tại thời điểm
    ghi; không cộng nhiều snapshot với nhau thành tổng views.

## Kiểm soát quy trình

| Chuyển đến | Điều kiện |
|---|---|
| Nghiên cứu | Có brief |
| Thumbnail | Có file dữ liệu nghiên cứu |
| Clip Flow | Có thumbnail |
| Dựng video | Có clip |
| Kiểm duyệt | Có thành phẩm main; không còn render đang chờ/chạy |
| Sẵn sàng | Đã duyệt đủ bốn mục QC cho phiên bản thành phẩm hiện tại |
| Đã lên lịch | QC phù hợp, hash thành phẩm khớp, thời gian ở tương lai |
| Đã đăng | QC phù hợp, hash thành phẩm khớp, URL YouTube do người vận hành cung cấp |

Thay tài nguyên trong bước Kiểm duyệt/Sẵn sàng đưa dự án về Dựng video. Ở Đã lên lịch
phải yêu cầu chỉnh sửa trước khi thay file. Dự án Đã đăng giữ nguyên nguồn; tạo dự án
mới cho lần sản xuất tiếp theo. Hash phát hiện file bị thay ngoài hệ thống.

**Lưu phiên bản là lịch sử bản ghi + hash**, không phải kho lưu trữ bất biến của file.
Nếu tự ghi đè file gốc, phiên bản cũ sẽ không mở lại được với nội dung cũ; cần giữ file
nguồn mỗi bản ở đường dẫn riêng. Bản này không sao chép video hàng GB để tránh tăng
gấp đôi dung lượng. Các render của Hub có thư mục riêng theo mã tác vụ nên không ghi
đè kết quả render cũ.

## Bàn giao giữa các tool

Mỗi dự án có `data/projects/<project_id>/` chứa:

- `brief.txt`, `flow_prompt.txt`: brief và prompt gợi ý, cần xem lại trước khi dùng.
- `handoff.json`: kênh, dự án, nguồn và phiên bản.
- `editor_project.json`: dùng nút Mở dự án trong editor để nhận danh sách clip.
- `renders/<job_id>/`: log, thành phẩm và báo cáo engine cho từng lần chạy.

Mở Studio là một yêu cầu mở ứng dụng, **không đánh dấu đã tạo ảnh/clip thành công**.
Kết quả được chọn và nhập rõ vào dự án; Hub không đoán file mới nhất thuộc dự án nào.
Studio hiện tại chưa tự nhận handoff; chọn đúng ảnh/prompt từ thư mục này.

## Lỗi, hủy và thử lại

- Mỗi dự án chỉ có một render đang chờ/chạy; toàn bộ Hub dùng một worker.
- Hủy tác vụ chờ: chuyển thành cancelled. Hủy tác vụ chạy: yêu cầu engine dừng.
- Nếu ứng dụng dừng đột ngột, lượt đang chạy được ghi interrupted khi mở lại, không
  tự coi là thành công. Tác vụ queued vẫn được chạy lần sau.
- Thử lại tạo job mới, liên kết job cũ và chụp lại danh sách tài nguyên hiện tại.
- Nếu file nguồn bị thay so với hash, worker dừng trước khi render; nhập lại phiên bản.
- Xem lỗi trong hàng đợi và `render.log`. File kết quả một phần nếu có được giữ ở
  thư mục tác vụ, không tự động coi là tài nguyên được chấp nhận.

## Sao lưu và xuất hồ sơ

Nút **Backup DB** dùng SQLite Backup API để lấy bản nhất quán, gồm cả thay đổi đang
ở WAL. Bản backup không chứa file media. Cần sao lưu cả các thư mục media nguồn và
`data/projects` nếu muốn khôi phục đầy đủ. Để khôi phục, đóng Hub và giữ bản database
hiện tại, sau đó thay database bằng bản backup; việc này do người dùng thực hiện.

**Xuất hồ sơ JSON** chứa dự án, tài nguyên, hash, QC, chỉ số, jobs và audit để làm
bằng chứng hoặc phân tích. Hồ sơ có đường dẫn cục bộ và nhãn người thao tác; xem lại
trước khi công khai trong báo cáo.

## Giới hạn đã chốt cho MVP

- Một người dùng cục bộ; tên người thao tác là nhãn audit, không phải danh tính đã
  xác thực. Chưa có RBAC hoặc cộng tác đồng thời qua mạng.
- Chưa tự đăng YouTube, chưa tự đồng bộ Analytics, chưa tự tạo nội dung trên Flow.
- Chưa có AI đề xuất chiến lược/SEO hoặc khẳng định video sẽ hiệu quả.
- QC thị giác/âm thanh/quyền tài nguyên do người vận hành xác nhận. Hash chỉ chứng
  minh file không đổi, không chứng minh nội dung tốt hoặc quyền sử dụng hợp lệ.
- Phiên bản schema là 2; SQLite cục bộ, không dùng file DB trên thư mục share mạng.

## Kiểm thử và đóng gói

```
py -m unittest test_hub -v
py app.py --demo --self-check data/ui_selfcheck.json
```

Đóng gói bằng `build.bat`. Xem `KIEN_TRUC_VA_PHAM_VI.md` và `KE_HOACH_KHOA_LUAN.md`
để hiểu quyết định kiến trúc, phạm vi nghiệm thu và kế hoạch đánh giá.
