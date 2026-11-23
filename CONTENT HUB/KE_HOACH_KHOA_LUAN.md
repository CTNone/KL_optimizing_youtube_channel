# Kế hoạch hoàn thiện và đánh giá khóa luận

## Luận điểm kỹ thuật

Đề tài giữ tên: **Phát triển hệ thống quản trị quy trình sản xuất nội dung trên nhiều
kênh YouTube**. Đối tượng thử nghiệm: một người vận hành nhiều kênh. Đóng góp là mô
hình dữ liệu phân cấp kênh → album phát hành → video/mix, truy xuất nguồn/phiên bản,
playlist nhạc riêng từng video, QC, điều phối render, phục hồi và kết nối công cụ.
Google Flow là dịch vụ được tích hợp; không tuyên bố tự phát
triển mô hình sinh ảnh/video hoặc tự cải thiện hiệu quả kinh doanh của kênh.

## Brainstorm đã chuyển thành ưu tiên

| Vấn đề thực tế | Giải pháp sản phẩm | Cách kiểm chứng |
|---|---|---|
| Dễ nhầm file giữa các kênh/album | Mỗi video có project_id, channel_id và album_id | Lọc kênh/album, mở đúng nguồn và xuất hồ sơ |
| Dùng nhầm playlist giữa các video | Playlist Music Manager gắn riêng từng video | Hai video trong cùng album dùng hai playlist khác nhau |
| Không nhớ bản nào đã duyệt | QC gắn version thành phẩm | Đổi file sau QC, xác nhận bắt duyệt lại |
| Chuyển tool làm mất ngữ cảnh | Brief, nguồn và handoff theo dự án | Mở editor_project.json với đúng clip |
| Render lỗi khó tìm nguyên nhân | Job snapshot, log, lỗi và retry_of | Cố ý thiếu/sửa nguồn rồi thử lại |
| Đóng app không biết render xong chưa | Interrupted và kiểm tra output | Dừng thử nghiệm, mở lại DB demo |
| Báo cáo dựa vào cảm tính | Nhật ký và hồ sơ xuất JSON | Đối chiếu thao tác, thời gian và nguồn |

## Kịch bản bảo vệ 10–15 phút

1. Nêu vấn đề dữ liệu và quy trình phân tán; giới thiệu kiến trúc.
2. Mở DB demo, thể hiện ba kênh và các album phát hành.
3. Mở album có hai video/mix, cho thấy brief, playlist và trạng thái riêng từng video.
4. Mở video/mix, brief và trạng thái; thử chuyển bước khi thiếu nguồn để thấy gate.
5. Mở thư mục handoff, trình bày liên kết Flow Agent trên website, Music Manager và editor.
6. Render bản ngắn (ví dụ 0.1 phút = 6 giây) bằng clip mẫu đã chuẩn bị.
7. Hiển thị job, hash và thành phẩm; chuyển QC, duyệt checklist.
8. Nhập bản mới để minh họa vô hiệu hóa trạng thái duyệt.
9. Trình bày lịch đăng nội bộ, lịch sử thao tác và xuất hồ sơ.
10. Dùng video 1 giờ đã render trước làm bằng chứng thời lượng, không chờ render dài
   trong buổi bảo vệ. Phân biệt dữ liệu minh họa và dữ liệu thật.

## Thiết kế thực nghiệm đề xuất

Chuẩn bị tối thiểu ba kênh thử nghiệm, mỗi kênh 2–3 album với nhiều video/mix. Gắn
playlist khác nhau vào hai video cùng album để đánh giá cách ly nhạc. Dùng cùng bộ nguồn cho
quy trình thủ công và Hub. Tách thời gian thao tác của người dùng, thời gian máy xử
lý và thời gian chờ dịch vụ. Không so một lượt thủ công đầy đủ với một lượt Hub dùng
cache mà không ghi rõ điều kiện.

Thu thập:

- Thời gian tìm đúng nguồn/phiên bản, bàn giao và xác định trạng thái.
- Số thao tác chuyển tool/ghi thông tin và số lỗi gắn nhầm tài nguyên.
- Thời gian render, cấu hình máy, độ phân giải, codec, dung lượng và thời lượng nguồn.
- Tỷ lệ hoàn thành trên tập thử nghiệm đã mô tả; không suy rộng ra mọi nội dung.
- Các ca lỗi thiếu file, nguồn bị sửa, hủy, chạy lại và khởi động lại.
- QC điểm nối từ preview nhiều vòng; người đánh giá, tiêu chí và kết quả.

Công thức giảm thời gian thao tác: `(T_thủ_công - T_hệ_thống) / T_thủ_công × 100%`.
Chỉ điền số sau khi đo; chưa có bằng chứng để tuyên bố tỷ lệ tăng năng suất.

Ghi từng lượt và lưu bằng chứng theo [phiếu thực nghiệm khóa luận](PHIEU_THU_NGHIEM_KHOA_LUAN.md).
Database demo mới có 3 kênh, 6 album và 12 video/mix để chạy kịch bản; đây là dữ liệu
tổng hợp, không được dùng làm kết quả đo quy trình thực tế.

## Lộ trình tiếp theo

1. **Kiểm thử vận hành với dữ liệu thật:** đi hết một dự án, ghi vướng mắc, điều chỉnh UI.
2. **Bàn giao tự động có định danh:** bổ sung project_id vào request/manifest Studio,
   nhập kết quả theo ID chính xác; không dùng “file mới nhất” làm bằng chứng.
3. **Đóng băng phạm vi:** hoàn thiện theo dõi analytics sau đăng đã bổ sung; không thêm
   SEO/AI planner, tự đăng YouTube hay cộng tác nhóm vào MVP.
4. **Đánh giá và viết báo cáo:** use case, ERD, sequence job/QC, kiểm thử, thực nghiệm,
   giới hạn và hướng phát triển. Không mở thêm phân hệ trước khi quy trình chính ổn.

## Dàn ý báo cáo gợi ý

1. Tổng quan bài toán và công cụ liên quan.
2. Khảo sát nghiệp vụ, phạm vi, yêu cầu chức năng/phi chức năng.
3. Phân tích thiết kế: kiến trúc, dữ liệu, workflow, sequence và quyết định kỹ thuật.
4. Cài đặt và tích hợp: Store, adapter, queue, media engine và UI.
5. Kiểm thử, thực nghiệm, kết quả và phân tích giới hạn.
6. Kết luận và hướng mở rộng.

Các chỉ số YouTube chỉ là dữ liệu vận hành tham khảo. Hiệu quả views/doanh thu không
phải tiêu chí duy nhất để đánh giá chất lượng phần mềm và chưa có thiết kế nhân quả
để quy kết tăng trưởng kênh cho Hub.

---

## Kế hoạch triển khai chắc chắn đến tháng 12/2026

Kế hoạch này ưu tiên hoàn thiện và chứng minh MVP hiện có. Tính năng mới chỉ được nhận
vào khi sửa một lỗi cản trở luồng chính hoặc đáp ứng tiêu chí nghiệm thu bên dưới. Nếu
ngày bảo vệ được chốt sớm hơn, giữ nguyên thứ tự các giai đoạn và rút ngắn phần cải tiến,
không cắt thời gian đóng băng và chuẩn bị bằng chứng.

### Mục tiêu sản phẩm để nghiệm thu

Một người vận hành quản lý được nhiều kênh trên một máy Windows. Với mỗi video/mix, Hub
phải trả lời được: thuộc kênh/album nào, đang ở bước nào, cần tài nguyên nào, bản nào đã
được duyệt, và job gần nhất thành công hay lỗi vì sao. Luồng chuẩn là:

```text
Kênh → Album/đợt phát hành → Video/mix → Brief và tài nguyên
     → Dựng/job → QC theo phiên bản → Lịch nội bộ → Xác nhận URL đã đăng
```

Đây là hệ thống quản trị và điều phối. Tạo nội dung bằng AI, nghiên cứu thị trường,
đăng YouTube vẫn do người vận hành thực hiện. Hub đọc analytics sau đăng theo yêu cầu; CTR lấy từ báo cáo hằng ngày và có độ trễ.

### Phạm vi khóa đến ngày bảo vệ

**Bắt buộc hoàn thiện:** phân cấp kênh/album/video; lọc và trạng thái; điều kiện chuyển
bước; tài nguyên có dấu vết phiên bản; QC gắn với đúng file đã duyệt; hàng đợi render bền
vững; log/lỗi/hủy/thử lại/khởi động lại; lịch nội bộ; audit và xuất hồ sơ; demo tách biệt
database thật.

**Chỉ sửa nếu đang chặn luồng bắt buộc:** lỗi dữ liệu, mất trạng thái, gắn nhầm tài nguyên,
không thể phục hồi job, cài đặt/khởi chạy lỗi, hoặc lỗi khiến người dùng hiểu sai trạng
thái. Mọi thay đổi khác phải qua cổng quyết định phạm vi.

**Không đưa vào bản bảo vệ:** RBAC/cộng tác mạng, tự đăng hoặc đồng bộ YouTube API, AI SEO/
planner, tự phân tích trend, chatbot/Agent Flow riêng, thêm provider sinh nội dung, hoặc
viết lại editor/render engine. Giữ chúng trong danh sách hướng phát triển.

### Mốc triển khai

| Thời gian | Trọng tâm | Kết quả phải có để qua mốc |
|---|---|---|
| 04–10/11 | Chốt phạm vi, kiểm kê luồng hiện có và lập danh sách lỗi theo mức độ | Một backlog ngắn có tiêu chí hoàn tất; sơ đồ luồng và dữ liệu khớp với sản phẩm; không mở phân hệ mới |
| 11–20/11 | Làm chắc quy tắc nghiệp vụ và dữ liệu | Các chuyển bước có validation; QC vô hiệu khi file đổi; tài nguyên/job gắn đúng project; backup/restore và demo database có quy trình rõ |
| 21–30/11 | Làm chắc tích hợp và xử lý lỗi | Một ca render thành công, lỗi nguồn, hủy, retry và khởi động lại được ghi nhận; không báo thành công khi chưa xác minh output |
| 01–07/12 | Chạy thử nghiệm có kịch bản, chốt giao diện bảo vệ | Bộ dữ liệu demo đa kênh; số đo có cách thu thập và nguồn; kịch bản trình diễn chạy được từ đầu đến cuối |
| 08–14/12 | Đóng băng tính năng, hoàn thiện báo cáo và gói chạy | Bản phát hành ứng viên, hướng dẫn cài/chạy, ảnh/sơ đồ, kết quả kiểm chứng và giới hạn được ghi rõ |
| 15/12 đến ngày bảo vệ | Chỉ sửa lỗi nghiêm trọng và tập bảo vệ | Không có tính năng mới; bản demo dự phòng và dữ liệu dự phòng sẵn sàng |

Các mốc là lịch làm việc đề xuất từ ngày 04/11/2026, không giả định ngày bảo vệ chính
thức. Khi có lịch của khoa, dịch mốc tương ứng nhưng giữ tối thiểu 7 ngày cuối làm giai
đoạn đóng băng.

### Quy trình vibe coding có kiểm soát

Mỗi yêu cầu cho AI/coding agent phải có đủ: **bối cảnh → hành vi hiện tại → hành vi cần
có → tiêu chí chấp nhận → file/phạm vi được phép sửa → cách kiểm chứng**. Chia việc thành
thay đổi nhỏ, quan sát được; không giao một prompt kiểu “làm lại cho tốt hơn”.

1. Ghi một issue ngắn với lỗi hoặc nhu cầu người dùng và tiêu chí chấp nhận cụ thể.
2. Đọc đường đi dữ liệu hiện tại trước khi sửa; nêu module bị ảnh hưởng và nguy cơ migration.
3. Yêu cầu đề xuất thay đổi tối thiểu; không thêm dependency, bảng dữ liệu hay abstraction nếu chưa cần.
4. Sau khi sửa, xem diff và kiểm chứng đúng hành vi, gồm một ca lỗi liên quan. Ghi lệnh/kết quả vào nhật ký khóa luận.
5. Chỉ nhận thay đổi khi tiêu chí đạt, không làm hỏng luồng chính và tài liệu liên quan được cập nhật.
6. Nếu yêu cầu làm nảy sinh thêm phân hệ hoặc không thể kiểm chứng trong ngày, đưa vào backlog sau bảo vệ.

Không để AI tự mở rộng phạm vi, xóa dữ liệu, sửa schema không có migration, chạy tác vụ
Flow tiêu tốn credit, hoặc tuyên bố kiểm thử thành công khi chưa có kết quả quan sát được.

### Thiết kế để mở rộng sau bảo vệ

Giữ cấu trúc **modular monolith**: một ứng dụng desktop và một SQLite, nhưng mỗi miền có
trách nhiệm rõ. `store.py` giữ quy tắc và giao dịch dữ liệu; `services.py` điều phối job/
tích hợp; `app.py` chỉ trình bày và nhận thao tác. Không chuyển sang microservices hoặc
plugin framework trước khi có nhu cầu thực.

- Mỗi tích hợp ngoài có adapter riêng và nhận/gửi dữ liệu qua mô hình Hub ổn định. Flow,
  YouTube API hoặc dịch vụ khác có thể thay mà không đưa logic nhà cung cấp vào quy tắc workflow.
- Thay đổi schema phải tăng phiên bản và có migration lặp an toàn; giữ đường nâng cấp DB
  rõ ràng trước khi thêm trường/phân hệ.
- Giữ `channel_id`, `album_id`, `project_id`, `asset_id` và `job_id` làm định danh xuyên suốt;
  không ghép dự án bằng tên file hoặc “file mới nhất”.
- Ghi sự kiện nghiệp vụ và job theo project để sau này thêm người dùng, thông báo hoặc
  báo cáo mà không phải suy ra lịch sử từ trạng thái hiện tại.
- Chỉ mở rộng state machine, quyền người dùng, analytics hoặc đồng bộ API khi có yêu cầu
  nghiệp vụ và tiêu chí nghiệm thu riêng.

### Cổng phát hành và bằng chứng

Không coi “chạy được trên máy phát triển” là hoàn tất. Bản ứng viên phải qua checklist:

- Tạo/sửa/lọc ít nhất ba kênh; video thuộc đúng album và vẫn xem được dự án cũ.
- Thử chuyển bước khi thiếu điều kiện; hệ thống từ chối và giữ dữ liệu nhất quán.
- Thay file sau QC; duyệt cũ không còn hợp lệ.
- Chạy render ngắn thành công; sau đó thử nguồn lỗi, retry và phục hồi sau khi đóng/mở ứng dụng.
- Đối chiếu hồ sơ xuất với nội dung hiển thị, kiểm tra backup database demo và chạy trên môi trường sạch/đóng gói dự kiến.
- Lưu ảnh chụp, log, dữ liệu đầu vào, phiên bản phần mềm và kết quả cho từng ca; phân biệt dữ liệu thật với dữ liệu minh họa.

Đánh giá hiệu quả quản trị bằng thời gian tìm đúng trạng thái/nguồn, số lần chuyển công
cụ, số lỗi gắn nhầm tài nguyên và khả năng truy nguyên/phục hồi. Đo trên cùng bộ dữ liệu
và ghi riêng thời gian thao tác người dùng với thời gian render; không suy ra tác động
nhân quả lên lượt xem.
