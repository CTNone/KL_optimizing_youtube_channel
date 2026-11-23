# YouTube Content Hub — quản trị quy trình sản xuất đa kênh

Phiên bản desktop, dành cho **một người vận hành nhiều kênh YouTube**. Content Hub là
bảng điều hành danh mục: **kênh → đợt phát hành → từng video hoặc mix**. Một đợt phát hành có
thể gom nhiều video; mỗi video có brief, tài nguyên, QC và trạng thái xuất bản riêng.
Music Manager vẫn là nguồn chính cho thư viện nhạc và ghi công; CapCut được dùng để
biên tập video và ghép nhạc.

Hub dùng Flow Agent ngay trên website cho việc lên ý tưởng và tạo/chỉnh ảnh, video.
Hub chỉ bàn giao brief và tài nguyên; không tái tạo chat Agent hoặc bảng tạo Flow riêng.

## Mở phần mềm

- Cách dễ nhất: chạy `OPEN_CONTENT_HUB.bat` ở thư mục gốc dự án; phần mềm mở thẳng trang **Tổng quan**.
- Bản EXE có sẵn: `dist/dashboard_20261104_simple/YouTubeContentHub/YouTubeContentHub.exe`.
  Bản này được đóng gói trước tab Analytics; chạy `OPEN_CONTENT_HUB.bat` để dùng source mới,
  hoặc build lại nếu cần EXE có tính năng mới.
- Các bản EXE cũ được lưu trong `dist/archive/`; chạy `OPEN_CONTENT_HUB.bat` để mở bản mới.
- Bản source trong thư mục này: chạy `run.bat` (Python 3.10+ có tkinter).
- Demo riêng: `run_demo.bat`, hoặc EXE với tham số `--demo`.
- Database sản xuất: `data/content_hub.sqlite3`; database demo: `data/demo.sqlite3`.
  Demo không được trộn vào dữ liệu sản xuất.
- Database demo mới được seed với 3 kênh, 6 album và 12 video/mix. Seed có thể chạy lại
  để bổ sung mục mẫu còn thiếu; không ghi đè mục đã có và không tự nhập media từ thư mục
  output của người dùng. Database demo cũ được giữ nguyên, nên có thể còn các kênh, dự án
  hoặc tham chiếu media từ lần chạy trước; dùng database demo mới để có bộ mẫu sạch.
- Thư viện nhạc, ghi công và playlist theo kênh cũng dùng database sản xuất này.
  Music Manager lấy danh sách kênh từ Hub; nhạc cũ trong `editer/Nhạc jazz/Music_Manager/data/music.sqlite3`
  được nhập một lần khi mở database sản xuất và file nguồn được giữ nguyên.
- Handoff, bản backup và hồ sơ xuất được đặt trong `OUTPUT TỔNG/Content Hub/`.

Giữ CONTENT HUB cạnh TOOL NCTT và editer trong
workspace. Giữ `_internal` cạnh EXE. Python không cần để chạy Hub đóng gói; NCTT,
Music Manager và bản source của Tool Edit cần Python
cùng thư viện tương ứng.
Hub chỉ kết nối Google khi người vận hành chủ động mở tab Analytics và đăng nhập OAuth.
OAuth client và refresh token được lưu cục bộ trong `%LOCALAPPDATA%\YouTubeContentHub`; Hub
không cần API key.

## Bắt đầu nhanh cho người mới

Đi theo luồng **Tổng quan → video → tài nguyên → kiểm duyệt → đăng**. Chỉ mở công cụ
phụ khi công việc của bạn cần chúng.

1. Chạy `OPEN_CONTENT_HUB.bat`, chọn **Tạo kênh** và điền tên kênh. Ngách, URL và
   phong cách có thể bổ sung sau.
2. Chọn **Tạo đợt phát hành**, rồi tạo video/mix bên trong đợt đó. Đây là
   nhóm phát hành; mỗi video vẫn có brief, file và trạng thái riêng.
3. Mở video, ghi tên và mô tả nội dung. Trong tab **Sản xuất**, chọn **Mở Google Flow** để
   mở website cùng thư mục dự án. Tạo nội dung trên website, rồi quay lại Hub.
4. Vào **Tài nguyên → Nhập file** để thêm ảnh bìa, video clip và video hoàn chỉnh. Chọn đúng
   loại file trước khi nhập. Hub giữ file tại vị trí hiện tại và ghi mã kiểm tra để phát hiện file bị đổi.
5. Dùng CapCut để biên tập video và ghép nhạc. Sau đó nhập file thành phẩm vào Hub dưới
   loại **Video hoàn chỉnh**.
6. Mở **Kiểm duyệt & Đăng**, xem video, đánh dấu đủ các mục kiểm tra rồi bấm **Duyệt →
   Sẵn sàng**. Nhập lịch dự kiến hoặc đường dẫn sau khi tự đăng trên YouTube Studio.

Tab **Sản xuất** có thể mở Nghiên cứu thị trường, Quản lý nhạc, Google Flow và thư mục dự án.
Hub không gắn playlist cho từng video và không render video; hãy quản lý danh sách nhạc
trong Music Manager rồi nhập bản ghép hoàn chỉnh từ CapCut. Mở **Lịch sử** để xem thao tác;
dùng **Sao lưu dữ liệu** ở thanh trên để sao lưu.

## Theo dõi video sau đăng

Tab **Theo dõi video sau đăng** liệt kê dự án đã xác nhận đăng và có URL YouTube. Chọn
video rồi bấm **Làm mới chỉ số** để lưu snapshot lượt xem, thời gian xem tổng, thời lượng
xem trung bình, tỷ lệ xem trung bình, comment, like, share, impressions và CTR. Mỗi lần
làm mới được lưu vào lịch sử cục bộ.

Lần đầu, tạo project trong Google Cloud, bật YouTube Analytics API và YouTube Reporting API, cấu hình OAuth consent screen, tạo OAuth client loại **Desktop app**, rồi bấm
**Kết nối Google…** và chọn file JSON đã tải. Trong trình duyệt, đăng nhập tài khoản có
quyền xem Analytics của kênh và cấp scope chỉ đọc. Nếu consent screen đang ở chế độ
Testing, thêm tài khoản đăng nhập làm test user. Token/client JSON được giữ trong
`%LOCALAPPDATA%\YouTubeContentHub`, không ghi vào database hay hồ sơ xuất dự án. Dùng
**Ngắt kết nối & xóa snapshot** để thu hồi OAuth và xóa snapshot Analytics trong Hub.
Có thể xem/thu hồi quyền Google tại
[trang quyền bảo mật](https://security.google.com/settings/security/permissions).

CTR thumbnail và impressions lấy từ báo cáo hằng ngày YouTube Reporting API. Nút làm mới
nhập báo cáo mới nhất đang có, thường trễ 1–2 ngày; báo cáo mới có thể chưa xuất hiện
trong 1–2 ngày đầu. CTR được tính theo trọng số impressions trong tối đa 28 ngày có báo
cáo. Các chỉ số còn lại được truy vấn từ YouTube Analytics API theo video từ ngày tạo dự
án trong Hub; YouTube có thể điều chỉnh hoặc làm chậm số liệu. Hub không đăng video.

## Kiểm soát quy trình

| Chuyển đến | Điều kiện |
|---|---|
| Nghiên cứu | Có brief |
| Thumbnail | Có file dữ liệu nghiên cứu |
| Video clip | Có ảnh bìa |
| Dựng video | Có clip |
| Kiểm duyệt | Có video thành phẩm nhóm main |
| Sẵn sàng | Đã duyệt đủ bốn mục QC cho phiên bản thành phẩm hiện tại |
| Đã lên lịch | QC phù hợp, hash thành phẩm khớp, thời gian ở tương lai |
| Đã đăng | QC phù hợp, hash thành phẩm khớp, URL YouTube do người vận hành cung cấp |

Thay tài nguyên trong bước Kiểm duyệt/Sẵn sàng đưa dự án về Dựng video. Ở Đã lên lịch
phải yêu cầu chỉnh sửa trước khi thay file. Dự án Đã đăng giữ nguyên nguồn; tạo dự án
mới cho lần sản xuất tiếp theo. Hash phát hiện file bị thay ngoài hệ thống.

**Lưu phiên bản là lịch sử bản ghi + hash**, không phải kho lưu trữ bất biến của file.
Nếu tự ghi đè file gốc, phiên bản cũ sẽ không mở lại được với nội dung cũ; cần giữ file
nguồn mỗi bản ở đường dẫn riêng. Bản này không sao chép video hàng GB để tránh tăng
gấp đôi dung lượng.

## Bàn giao giữa các tool

Mỗi video/mix có `OUTPUT TỔNG/Content Hub/Projects/<project_id>/` chứa:

- `brief.txt`, `flow_prompt.txt`: brief và prompt gợi ý, cần xem lại trước khi dùng.
- `handoff.json`: kênh, dự án, nguồn và phiên bản.

Mở Flow là một yêu cầu mở website kèm thư mục bàn giao, **không đánh dấu đã tạo
ảnh/clip thành công**. Kết quả được chọn và nhập rõ vào đúng video/mix; Hub không
đoán file mới nhất thuộc dự án nào. NCTT và Music Manager vẫn là ứng dụng độc lập,
được mở với ngữ cảnh kênh/video khi có thể. Biên tập và xuất video được thực hiện trong CapCut.

## Sao lưu và xuất hồ sơ

Nút **Sao lưu dữ liệu** dùng SQLite Backup API để lấy bản nhất quán, gồm cả thay đổi đang
ở WAL. Bản backup không chứa file media. Cần sao lưu cả các thư mục media nguồn và
`OUTPUT TỔNG/Content Hub/Projects` nếu muốn khôi phục đầy đủ. Để khôi phục, đóng Hub và giữ bản database
hiện tại, sau đó thay database bằng bản backup; việc này do người dùng thực hiện.

**Xuất hồ sơ JSON** chứa dự án, tài nguyên, hash, QC, chỉ số, jobs và audit để làm
bằng chứng hoặc phân tích. Hồ sơ có đường dẫn cục bộ và nhãn người thao tác; xem lại
trước khi công khai trong báo cáo. OAuth và snapshot YouTube Analytics không nằm trong hồ sơ xuất.

## Bàn giao cho phiên làm việc AI tiếp theo

Đọc [`AI_HANDOFF.md`](AI_HANDOFF.md) trước khi thay đổi Analytics. Tài liệu này ghi quyết
định đã chốt, vị trí mã, cấu hình API và các phần chưa xác nhận bằng tài khoản thật.
Phạm vi tổng thể nằm trong [`KIEN_TRUC_VA_PHAM_VI.md`](KIEN_TRUC_VA_PHAM_VI.md) và
[`KE_HOACH_KHOA_LUAN.md`](KE_HOACH_KHOA_LUAN.md).

## Giới hạn đã chốt cho MVP

- Một người dùng cục bộ; tên người thao tác là nhãn audit, không phải danh tính đã
  xác thực. Chưa có RBAC hoặc cộng tác đồng thời qua mạng.
- Chưa tự đăng YouTube hoặc tự tạo nội dung trên Flow. Analytics chỉ đọc theo yêu cầu;
  CTR đến từ báo cáo hằng ngày và có độ trễ.
- Chưa có AI đề xuất chiến lược/SEO hoặc khẳng định video sẽ hiệu quả.
- QC thị giác/âm thanh/quyền tài nguyên do người vận hành xác nhận. Hash chỉ chứng
  minh file không đổi, không chứng minh nội dung tốt hoặc quyền sử dụng hợp lệ.
- Phiên bản schema là 5; thêm dữ liệu snapshot Analytics theo cách tương thích database cũ.
  Lớp album/playlist không xóa hoặc chuyển đổi dự án/video cũ.
  SQLite cục bộ, không dùng file DB trên thư mục share mạng.

## Kiểm thử và đóng gói

```
py -m unittest test_hub -v
py app.py --demo --self-check data/ui_selfcheck.json
```

Đóng gói bằng `build.bat`. Xem `KIEN_TRUC_VA_PHAM_VI.md` và `KE_HOACH_KHOA_LUAN.md`
để hiểu quyết định kiến trúc, phạm vi nghiệm thu và kế hoạch đánh giá.
