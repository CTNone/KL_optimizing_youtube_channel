# NCTT + Thumbnail — Desktop 1.0, điều khiển Flow trực tiếp

Mở shortcut **NCTT + Thumbnail** trên Desktop. Bản này không cần cài/bật Chrome extension, không gửi việc sang panel Flow TXT và không dùng Native Messaging. Python/Playwright điều khiển Chrome trực tiếp. Bộ chọn mô hình, số ảnh, theo dõi tạo ảnh, retry, phát hiện lỗi và tải 2K dùng chung mã nguồn đã kiểm thử; bộ lưu/cắt ảnh chạy trực tiếp trong Python.

## Bắt đầu

### Dùng Chrome đang mở và phiên đăng nhập hiện tại

1. Mở hồ sơ Chrome của bạn như bình thường và mở dự án Flow.
2. Trong Chrome 144 trở lên, mở `chrome://inspect/#remote-debugging` và bật **Allow remote debugging for this browser instance**. Đây là quyền kết nối do Chrome yêu cầu; tool không tự bật.
3. Trong Desktop, chọn hồ sơ tại **Hồ sơ Chrome đang dùng**, bấm **Kết nối Chrome đang mở**, rồi bấm **Allow** trong Chrome nếu có yêu cầu.
4. Nếu Chrome có nhiều tab Flow, chọn đúng tab dự án trong danh sách của tool. Hồ sơ Chrome cùng thư mục User Data có thể dùng chung một tiến trình, nên danh sách có thể gồm tab từ các hồ sơ khác; xác nhận đúng tab và account trước khi chạy.
5. Nhập prompt, chọn ảnh mẫu nếu cần và bấm **Tạo ảnh**. Không cần nhập phiên hoặc đăng nhập lại. Nếu đổi hồ sơ, kết nối và chọn lại tab; nếu đổi account trong cùng tab, đặt lại hạn mức.

Tool kết nối endpoint cục bộ do Chrome cung cấp qua DevToolsActivePort; không mở Chrome mới, không sao chép cookie. Đóng tool chỉ ngắt kết nối, giữ Chrome hiện tại mở. Khi Chrome chưa bật quyền hoặc không cung cấp endpoint, tool hướng dẫn bật và không tự chuyển sang hồ sơ riêng. Hướng dẫn chính thức: https://developer.chrome.com/docs/devtools/agents/use-cases/auto-connect . Đã kiểm thử kết nối, tải/cắt ảnh, ngắt và kết nối lại bằng Chrome thật với hồ sơ thử cục bộ; chưa kiểm thử trên phiên Google thật.

Desktop chạy ở nhịp quan sát: dừng 1,2 giây trước thao tác bấm, chờ 2,4 giây sau đính kèm ảnh và ít nhất 3,6 giây sau gửi. Phải thấy Flow nhận lệnh (prompt đã xóa hoặc nút gửi chuyển sang trạng thái khóa/bận), rồi chờ kết quả mới ổn định trước khi tải. Ảnh có sẵn và ảnh mẫu không được tính là kết quả mới. Nếu chưa xác nhận gửi, tool dừng không tải, không tự gửi lại. Mỗi ảnh chỉ yêu cầu tải 2K một lần; lỗi lưu file được thử lại trên dữ liệu đã tải. Sau khi lưu, tool đóng bản xem và đưa focus về ô prompt; nếu không xác nhận được giao diện sẵn sàng, tool báo rõ.

Kết quả được đếm lại trên giao diện mỗi lần kiểm tra, không cộng dồn URL của các ảnh xem trước đã bị thay thế. Bản trùng được gộp theo mã asset/media hoặc URL chuẩn hóa; loại vùng ảnh đính kèm và ảnh đã có ngay trước khi bấm gửi. Nếu Flow tạm hiển thị nhiều bản xem trước, tool tiếp tục chờ đến khi số kết quả ổn định đúng x1–x4, không dừng ngay và không tự tạo lại. Hết thời gian vẫn không xác định đúng số ảnh thì dừng để tránh tải nhầm.

### Dùng hồ sơ Desktop riêng (tùy chọn)

1. Đóng ứng dụng Desktop cũ, mở lại shortcut. Tab Làm thumbnail có nút **Tạo ảnh trực tiếp trên Flow**.
2. Giữ hồ sơ `account-1` và bấm **Mở Google Flow · đăng nhập**.
3. Đăng nhập thủ công trong cửa sổ Chrome mới của Desktop và mở một dự án Flow. Chỉ giữ một tab Flow trong cửa sổ này.
4. Chọn ảnh mẫu từ thư viện NCTT hoặc từ máy tính. Có thể bỏ ảnh và chỉ dùng prompt. Ảnh PNG/JPG/WebP tối đa 20 MB; file nguồn được giữ nguyên.
5. Nhập prompt hoặc mở TXT; chọn mô hình, số ảnh x1–x4 và thư mục lưu bằng đường dẫn Windows đầy đủ.
6. Bấm **Tạo ảnh trực tiếp trên Flow**. Tool F5 và chờ thêm 2 giây sau khi tải xong, áp dụng mô hình/số ảnh, tải file ảnh thật, xác nhận thêm vào câu lệnh rồi gửi.
7. Xem tiến trình, thông báo, lịch sử, hạn mức và hai đường dẫn file ở tab **Trạng thái & lịch sử**. Có nút Dừng; lỗi lưu ảnh không tạo lại prompt.

## Đổi tài khoản

Hết lượt: Dừng và chờ lượt kết thúc, đổi account bằng giao diện Google trong cửa sổ Chrome của Desktop. Sau khi đổi, bấm **Đã đổi account · đặt lại hạn mức**, mở lại dự án và tiếp tục.

Muốn giữ phiên đăng nhập của nhiều account: nhập `account-2`, `account-3`, … ở ô hồ sơ và bấm Mở Flow. Mỗi hồ sơ lưu phiên Chrome, lịch sử và bằng chứng hạn mức riêng. Không đổi hồ sơ khi đang chạy. Account cùng một hồ sơ phải đặt lại hạn mức thủ công sau khi đổi; tool không suy đoán account Google.

Chrome Desktop dùng hồ sơ riêng trong `desktop-data/<hồ sơ>/chrome-profile`. Playwright không hỗ trợ điều khiển trực tiếp hồ sơ Chrome Default: https://playwright.dev/python/docs/api/class-browsertype . Đăng nhập/CAPTCHA/chặn quota cần người dùng xử lý.

### Nhập phiên Chrome có sẵn

Tool tự đếm và liệt kê hồ sơ Chrome khi mở giao diện: chọn tại **Hồ sơ Chrome trên máy**, bấm **Quét lại hồ sơ Chrome** khi vừa thêm/xóa hồ sơ. Quét chỉ đọc thông tin tên và kiểm tra thư mục hồ sơ, không nhập cookie tự động. Hồ sơ Desktop `account-1`… là các hồ sơ riêng, không tính vào số Chrome nguồn.

Bấm **Nhập phiên từ Chrome…**, đóng Chrome nguồn (kể cả tiến trình nền), rồi đặt tên hồ sơ mới, ví dụ `chrome-import`. Tool dùng hồ sơ đã chọn trong danh sách; nếu không tìm thấy hồ sơ, có thể chọn thư mục thủ công. Có thể xem đường dẫn hồ sơ đang dùng tại `chrome://version`. Tool sao chép cookie và dữ liệu phiên sang hồ sơ riêng rồi mở Flow; không sửa nguồn, không ghi đè hồ sơ đã có, không sao chép kho mật khẩu hoặc lịch sử duyệt web. Cửa sổ Chrome của tool đang mở sẽ được đóng trước khi nhập, nên lưu công việc trong cửa sổ đó trước.

Danh sách mô hình hiện tại: **Nano Banana Pro**, **Nano Banana 2.1**, **Nano Banana 2 Lite**. Cấu hình cũ chọn đúng `Nano Banana 2` được chuyển sang `Nano Banana 2.1`; lịch sử và bằng chứng hạn mức cũ giữ nguyên. Tool xác nhận tên thực tế trên Flow trước khi gửi.

Việc nhập không đảm bảo giữ đăng nhập: mã hóa cookie của Chrome và kiểm tra của Google có thể yêu cầu đăng nhập lại (https://security.googleblog.com/2024/07/improving-security-of-chrome-cookies-on.html). Tool không giải mã cookie. Sau khi đăng nhập thành công, dùng lại cùng tên hồ sơ để giữ phiên cho lần mở sau. Kiểm thử nhập dùng dữ liệu giả; chưa xác nhận tái sử dụng phiên Google thật trên máy này.

Ô prompt có thanh cuộn dọc ở cạnh phải; hỗ trợ cuộn bằng bánh xe chuột và kéo thanh cuộn khi nội dung dài.

Ảnh mẫu được chọn theo lần upload mới nhất, không bắt buộc khớp tên file. Trước khi upload, tool ghi nhận các ảnh đã có; trong khi còn yêu cầu upload hoặc giao diện báo đang tải/xử lý thì chưa chọn. Khi hết trạng thái bận và ổn định 2 giây, tool chọn ảnh mới xuất hiện gần nhất trong cửa sổ thêm ảnh rồi bấm Thêm vào câu lệnh. Theo dõi thay đổi DOM giúp chọn được khi Flow đổi tên ảnh; không quét theo vị trí nth trong danh sách. Ảnh có sẵn trước upload không được chọn thay khi ảnh mới chưa xuất hiện. Sau khi bấm Thêm vào câu lệnh, tool xác nhận một ảnh mới xuất hiện trong ô prompt và không còn ảnh đính kèm cũ. Không so điểm ảnh giữa file nguồn và thumbnail của Flow vì Flow có thể cắt, nén hoặc đổi kích thước. Vùng nhận diện ưu tiên container của ô prompt, tránh nhận nhầm ảnh trong thư viện.

Chờ upload ảnh mẫu tối đa 5 phút: theo dõi yêu cầu mạng upload và trạng thái progress/busy/đang tải của Flow. Khi hết trạng thái bận, chờ ổn định thêm 2 giây rồi mới chọn ảnh. Log cập nhật mỗi 10 giây. Sau khi bấm Thêm vào câu lệnh, chờ tối đa 60 giây để xác minh ảnh đúng trong composer. Hết thời gian thì dừng, không gửi prompt và không tự upload lại. Nút Dừng vẫn dùng được khi chờ.

## Kết quả và cài đặt

Trong **Chuẩn bị tạo**, chọn **Tỉ lệ ảnh trên Google Flow**: 16:9, 4:3, 1:1, 3:4 hoặc 9:16. Mặc định Desktop là 4:3. Tool đặt tỉ lệ trong menu Flow và xác nhận trạng thái đang chọn trước khi upload/gửi prompt; log hiển thị tỉ lệ đã xác nhận. Extension có cùng lựa chọn. Nếu không đọc hoặc xác nhận được tỉ lệ, tool dừng trước khi gửi. Nên ghi tỉ lệ trong prompt đồng nhất với lựa chọn này. Ảnh gốc giữ nguyên file Flow tải về; bản cắt luôn là 16:9 (với nguồn 4:3, cắt 25% dưới; các tỉ lệ khác theo khung 16:9 neo trên lớn nhất).

- Ảnh gốc: `run_…/0001_01.jpg` (đuôi theo file gốc).
- Bản crop: `run_…/0001_01_16x9.jpg`.
- 4:3 → bỏ 25% dưới; ảnh không đúng 4:3 được cắt khung neo trên lớn nhất đúng 16:9, điều chỉnh vài pixel nếu cần.
- Không ghi đè file. Hash chống tính hai file giống nhau trong một lượt. Lỗi crop giữ bản gốc đã lưu và thử crop lại trên file đó.
- Hạn mức mô hình: chỉ khóa sau ít nhất 3 lỗi quota có bằng chứng sau khi gửi; event cùng lượt/attempt không đếm hai lần.
- Cài đặt nâng cao cho timeout, CSS ô prompt/nút gửi/số ảnh/kết quả/Download/2K và link ảnh gốc; lưu `desktop-settings.json`.
- Trạng thái và lịch sử từng hồ sơ lưu tại `desktop-data/<hồ sơ>/state.json`; bản tải tạm nằm dưới `downloads` cùng hồ sơ.
- Tab nghiên cứu tiếp tục dùng app.py của TOOL NCTT và dữ liệu/báo cáo cũ.

## Kiểm thử và cài máy khác

Đã kiểm thử bằng Chrome headless thật trên trang giả lập cục bộ, không cài extension: nút + SVG không nhãn → file chooser → tải file thật → thêm vào prompt; toàn bộ core → gửi đúng một lần → tải JPEG 2K → lưu gốc/crop và lịch sử. Kiểm thử quota, F5/chờ 2 giây/retry tối đa một lần, cancel, giữ bản gốc và crop retry đã đạt. Chưa chạy tạo ảnh trực tiếp trên Flow đăng nhập của người dùng.

Máy hiện tại đã cài Playwright và các thư viện Python. Máy khác cần Google Chrome, Python 3.10+ và `python -m pip install -r desktop-requirements.txt`; dùng Chrome đã cài nên không cần tải Chromium của Playwright. Giữ TOOL NCTT cạnh TOOL THUMBNAIL. Khởi chạy `Start-Studio.ps1`; shortcut hiện tại đã trỏ tới file này. Không chia sẻ thư mục desktop-data vì chứa phiên đăng nhập và lịch sử.
