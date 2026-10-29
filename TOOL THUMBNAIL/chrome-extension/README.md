# Flow TXT 0.10.0 — Upload ảnh tham chiếu qua Chrome

Chọn ảnh trực tiếp trên panel hoặc nhận từ NCTT. Flow asset picker được mở bằng + nếu cần; ảnh được tải bằng DOM.setFileInputFiles hoặc Page.fileChooserOpened được chặn để cấp file thật. Bấm Thêm vào câu lệnh khi xuất hiện, xác nhận preview nhỏ cạnh prompt; preview lớn trong picker không đủ để cho phép gửi. Native host chuẩn bị JPEG tham chiếu theo hash trong reference-cache. Desktop được bố trí lại thành thư viện/ý tưởng/cài đặt với bộ lọc ảnh. Đóng panel và ứng dụng cũ, tải lại extension **0.10.0**. Không cần đăng ký lại native host.

API được đối chiếu tài liệu Chrome DevTools Protocol: https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-setFileInputFiles và https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-setInterceptFileChooserDialog .

Ứng dụng tích hợp ở `../integrated_app.py`, hướng dẫn `../INTEGRATION.md`. Panel có nút **Nhận prompt + ảnh từ NCTT**, xem trước và bỏ ảnh tham chiếu. Chuyển dữ liệu không tự gửi prompt; vẫn kiểm tra và bấm Tạo ảnh. Upload ảnh được xác nhận bằng preview mới trước khi gửi. Giữ đầy đủ luồng cũ khi không dùng ảnh mẫu. Tải lại extension và đóng panel cũ để dùng host đã cập nhật.

Shortcut **Flow TXT.lnk** trên Desktop chạy `desktop/Start-FlowTXT.ps1` bằng PowerShell ẩn, mở Chrome hồ sơ Default tại trang khởi động của extension ligfchdeobjmdgdojlmogfpjnjlibgnh. Trang khởi động tự kết nối duy nhất một tab Flow và mở chính panel.html trong cửa sổ riêng. Giao diện, chrome.storage, bộ điều khiển, native host và luồng lưu gốc/16:9 đều dùng chung với nút extension. Khi panel đã mở, cả hai lối vào chỉ đưa panel đó lên trước, giữ prompt và thư mục của phiên hiện tại. Nếu chưa mở Flow hoặc có nhiều tab Flow, trang khởi động giữ nút thử kết nối và hiện lỗi; không tự gửi prompt.

Tải lại extension ở chrome://extensions, đóng panel cũ rồi nhấp shortcut. Chrome và extension vẫn phải được cài/bật trong đúng hồ sơ; đây là cửa sổ ứng dụng dùng extension hiện có. Muốn dùng hồ sơ khác, chạy Create-Shortcut.ps1 với -Profile 'Profile 1' và -Destination thư mục Desktop thực tế. Di chuyển dự án thì tạo lại shortcut. Đã kiểm tra đường dẫn Unicode của shortcut và kiểm thử dùng chung panel; chưa kiểm tra khởi chạy giao diện thực tế sau khi tải lại extension.

Bộ ghi Chrome folder nay chấp nhận đúng hậu tố `_16x9`, vốn bị bộ kiểm tra tên file của 0.7.0 từ chối với lỗi “Dữ liệu lưu ảnh không hợp lệ”. Test ghi bản cắt, xử lý tên trùng và chặn hậu tố/đường dẫn ngoài quy tắc đã đạt. Đóng panel cũ và tải lại extension để dùng **0.7.1**.

Sau tải 2K thông thường từ Flow, giữ nguyên file gốc và lưu thêm `_16x9.jpg` trong cùng thư mục cho cả Windows, Chrome folder và Downloads. Cắt khung lớn nhất đúng 16:9 neo ở phía trên: ảnh 4:3 bỏ đúng 25% chiều cao dưới; kích thước lẻ có thể bỏ thêm dưới 16 pixel chiều ngang để đúng tỉ lệ. Với nguồn không phải 4:3, mức cắt theo kích thước thực tế để được 16:9 (không thể đồng thời luôn cắt 25%). Bản cắt JPEG chất lượng 95, không kéo giãn ảnh. Panel/lịch sử hiển thị cả hai đường dẫn nhưng số ảnh tạo tính theo bản gốc. Lỗi cắt thử lại trên file đã tải/lưu, không tạo lại ảnh. Bản gốc vẫn được giữ nếu cắt thất bại.

Đóng panel cũ, tải lại extension và mở panel phiên bản **0.7.0** để bộ lưu Windows khởi động lại với mã mới; không cần cài lại native host. Chức năng áp dụng đường tải 2K mặc định; cấu hình link ảnh gốc nâng cao không đi qua bước xử lý tải cục bộ này. Kiểm thử file thực bằng Pillow xác nhận crop 2048×1536 → 2048×1152 và byte bản gốc không đổi.

Cả nút mở cài đặt và nút mở danh sách mô hình đã được nhận diện đều dùng DOM như dòng lựa chọn. Sau thao tác đầu, chờ và đọc lại combobox mới do Flow dựng trong portal; không yêu cầu danh sách xuất hiện ngay từ lớp cài đặt đầu tiên. Test mô phỏng portal xuất hiện trễ xác nhận ba thao tác mở cài đặt → mở danh sách → chọn Lite, mỗi thao tác một lần. Chưa xác minh trực tiếp trên Chrome của người dùng. Tải lại extension và đóng panel cũ; phiên bản **0.6.6**.

Log thực tế đã xác nhận tìm đúng BUTTON role=menuitem của Lite nhưng hit-test chuột bị từ chối. Các dòng mô hình được FlowModels khớp duy nhất nay dùng element.click() sau khi kiểm tra còn kết nối, hiển thị và không bị khóa. Nhánh này chỉ áp dụng các option mô hình đã nhận diện; gửi/tải vẫn theo chế độ hiện tại. Sau khi đóng menu, tool phải xác nhận nhãn mô hình trước khi gửi. Test tích hợp chế độ native xác nhận mở menu/gửi bằng Chrome và chọn Lite bằng DOM. Chưa xác nhận tương tác trên Chrome thực tế. Tải lại extension, đóng panel cũ và kiểm tra **0.6.5**.

Nhận diện thêm các dòng button không có role menu và chữ icon Material Symbols như banana/check quanh tên mô hình. Sau khi bấm, đóng menu rồi xác nhận lại nhãn mô hình trên Flow trước khi gửi. Lỗi bấm dòng mô hình ghi rõ tên mô hình, tag và role để đối chiếu. Kiểm thử mô phỏng nhóm dòng có chữ icon đã đạt; chưa xác nhận DOM trên Chrome thực tế của người dùng.

Panel không tự mở cài đặt khi khởi động. Kiểm tra thủ công đóng menu bằng Escape thay vì bấm ô prompt bị che. Menu mô hình hỗ trợ cả các dòng DIV/SPAN không có role: chỉ nhận nhóm dòng anh em có ít nhất hai tên mô hình chính xác khác nhau. Mỗi dòng được nhận diện giữ vùng bấm riêng, tránh lấy combobox cha làm mục tiêu. Sau khi chọn vẫn phải xác nhận mô hình thực tế trước khi gửi. Tải lại extension và đóng panel cũ; kiểm tra phiên bản **0.6.3**.

Sau F5, tool chờ trang báo tải xong rồi đợi thêm tối thiểu **2 giây** trước khi nạp bộ điều khiển, chọn mô hình hoặc gửi prompt. Sự kiện tải xong lặp lại chỉ khôi phục một lần. Bấm Dừng trong thời gian chờ sẽ hủy khôi phục; tab và URL dự án được kiểm tra lại sau khi chờ. Panel khóa Tạo ảnh/Kiểm tra khi đang F5, đang chạy hoặc đang kiểm tra mô hình; các lượt cập nhật trạng thái không chạy chồng nhau.

Tải lại extension, đóng bảng tool cũ rồi kết nối lại và kiểm tra **0.6.2**. Không cần cài lại bộ lưu Windows. Các kiểm thử là mô phỏng; chưa xác minh trực tiếp trên Chrome đăng nhập Flow.

## Nền tảng 0.6.1 — Chọn mô hình trong menu Flow đang mở

Ảnh chụp thực tế xác nhận tên **Nano Banana 2 Lite**. Tool chuyển cấu hình tên cũ “Nano Banana Lite” sang tên chính xác này. Khi danh sách mô hình đang mở, chọn trực tiếp mục tương ứng, không bấm lại nút mở menu bị danh sách che. Nhận diện mô hình đang chọn ưu tiên combobox thay vì mục đang hover/đánh dấu. Đóng menu bằng Escape trước bước nhập prompt. Các role combobox, menuitemradio và radio được kiểm tra đúng như điều khiển riêng. Có test mô phỏng menu ba dòng nằm trên ô prompt, trigger bên dưới bị che, và trường hợp dòng menu có một nút con.

Tải lại extension, đóng bảng tool cũ, F5 Flow, kết nối lại và kiểm tra **0.6.1**. Không cần cài lại bộ lưu Windows. Bộ test vẫn là mô phỏng; chưa kiểm thử tương tác trực tiếp trên Chrome đăng nhập.

## Nền tảng 0.6.0 — F5 trước lượt đầu, giữ mô hình và chống tải trùng

- Khi bấm Tạo ảnh, lưu prompt, số ảnh và mô hình rồi **F5 trước lần gửi 1**. F5 chuẩn bị không tính là lần thử 2. Lượt lỗi tạo có thể dùng thêm một F5 cho lần thử 2; lỗi lưu không tạo lại.
- Chọn mô hình cụ thể như **Nano Banana Lite** thì áp dụng lại sau mỗi F5, giữ nguyên cả lần thử 2 và xác nhận trước khi gửi. Không tự thay bằng Nano Banana 2. Chế độ thứ tự ưu tiên vẫn cho phép hạ mô hình khi lỗi tạo.
- Mỗi ảnh đều được mở riêng, xác minh URL/ID ảnh đang xem khớp ảnh cần tải trước khi bấm Download. Không khớp thì dừng để tránh lấy lại ảnh trước.
- Các chế độ Windows, Chrome folder và Downloads đều kiểm tra file Chrome đã tải trên máy bằng bộ hỗ trợ cục bộ. Không fetch lại URL ảnh từ content script; tránh lỗi CORS/`Failed to fetch`. Chế độ folder nhận dữ liệu từng phần dưới giới hạn thông điệp Native Messaging.
- Lỗi kiểm tra/ghi file thử lại trên **file đã tải**, không Download thêm cùng ảnh. Kiểm tra SHA-256 chống ghi/tính hai file có cùng dữ liệu trong một lượt. Chrome có thể đã nhận bản tải trùng trước khi kiểm tra hash; tool không tự xóa file Downloads.
- Bộ hỗ trợ đã đăng ký vẫn dùng được, không cần chạy lại installer. Đóng bảng tool cũ, tải lại extension, F5 Flow, kết nối lại và kiểm tra **0.6.0**.

Các mô tả bên dưới là nền tảng 0.5.x; quy tắc 0.6.0 ở trên được ưu tiên.

Sửa lỗi dừng tại Download khi ảnh có lớp SPAN/DIV hover: xác định đúng vùng ảnh, chọn điểm khác nếu tooltip che giữa nút, chờ điểm ổn định và đọc lại nút nếu Flow dựng lại nó. Chỉ thử bấm lại khi Chrome xác nhận chưa phát thao tác nhấn; không tự bấm lại khi kết quả nhấn không chắc chắn. Hộp thoại/lớp che khác vẫn chặn thao tác. Khi đã thấy ảnh mới, mọi lỗi tải/lưu không được kích hoạt F5/tạo lại. Lỗi đóng bản xem không làm mất kết quả 2K đã xác minh.

## Hành vi hiện tại

- Một file TXT là một prompt. Có thể sửa hoặc nhập prompt trực tiếp trong tool.
- Ba mô hình mặc định: **Nano Banana Pro → Nano Banana 2 → Nano Banana Lite**. Chọn mô hình cụ thể hoặc dùng thứ tự ưu tiên. Tool hiển thị mô hình trên Flow và mô hình sẽ dùng; mở cài đặt để đọc khi nhãn bị ẩn. Nhãn đã đọc là lần xác minh gần nhất, không phải thông tin về quota trên máy chủ.
- Trước khi gửi, tool đặt số ảnh x1–x4 trên Flow đúng với số ảnh trong tool và xác nhận lại. Không xác nhận được thì không gửi.
- Khi mô hình ưu tiên đã được chọn, không mở/chọn lại menu một cách thừa. Menu được chờ theo trạng thái DOM thay vì chỉ đợi cố định 350 ms.
- Lịch sử giữ trạng thái mở và không dựng lại khi dữ liệu không đổi. Chi tiết có lỗi từng lần, mô hình, file đã lưu và prompt. Lỗi chuẩn bị trước khi gửi cũng được ghi.
- **Hạn mức mô hình** chỉ liệt kê mô hình có ít nhất 3 lần Flow báo hạn mức rõ ràng sau khi gửi. Không mặc định khóa Pro. Không đếm lại cùng một lần thử; lỗi lưu, timeout, lỗi chính sách, lỗi tạo chung không chứng minh hết lượt.
- Thông báo lỗi cũ trên trang không làm thất bại lượt mới; thông báo mới vẫn được theo dõi. Hết credit tài khoản vẫn chặn, kể cả sau F5.
- Tải qua **mở ảnh → Download → 2K** và kiểm tra cạnh dài tối thiểu 2048 px. Không thay bằng thumbnail/1K, không chọn mục có phí/nâng cấp rõ ràng. Việc 2K miễn phí và khả dụng phụ thuộc menu Flow của tài khoản; chưa xác minh trực tiếp tài khoản thật trong phiên này.
- Flow tải một bản vào Chrome Downloads; chế độ Windows đọc đúng file đó, xác minh định dạng/kích thước rồi ghi cùng dữ liệu vào thư mục đã chọn. Không phóng lớn ảnh bằng tool. Bản Downloads được giữ.
- Lỗi lưu được thử lại trên ảnh đã tạo, không F5 để tạo thêm ảnh vì lỗi lưu. Giữ ảnh lưu thành công một phần. Lỗi tạo/timeout/chính sách có thể dùng lần thử thứ hai; timeout vẫn có nguy cơ tác vụ máy chủ chưa kết thúc.

## Đường dẫn Windows đầy đủ

Chế độ **Thư mục Windows** dùng Native Messaging của Chrome. Bộ hỗ trợ chỉ cho đúng ID extension đã đăng ký kết nối, và chỉ ghi ảnh trong thư mục chọn bằng hộp thoại Windows. Không có HTTP server hoặc quyền chọn đường dẫn tùy ý từ trang Flow.

Đăng ký một lần trong PowerShell tại thư mục `chrome-extension`:

```powershell
.\native-host\install.ps1 -ExtensionId ligfchdeobjmdgdojlmogfpjnjlibgnh
```

Script tạo manifest/launcher ngay trong `native-host` và đăng ký `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.flowtxt.files`. Python cần tkinter và Pillow; mặc định dùng runtime đi kèm Codex nếu có. Có thể truyền `-PythonPath` để dùng Python khác phù hợp. Di chuyển dự án hoặc đổi ID extension thì đăng ký lại.

Sau đó tải lại extension ở `chrome://extensions`, chấp thuận quyền Native Messaging nếu Chrome hỏi, đóng bảng điều khiển cũ, F5 tab Flow và kết nối lại. Kiểm tra phiên bản **0.5.1**. Chọn **Thư mục Windows**, bấm **Chọn thư mục Windows…**; đường dẫn hiển thị lấy trực tiếp từ hệ điều hành, ví dụ `C:\Users\CTN_Number_ONE\Documents\OUTPUT`.

Chế độ chọn qua Chrome vẫn chỉ hiển thị tên thư mục theo API trình duyệt. Chế độ Downloads hiển thị đường dẫn thực tế của file sau khi tải xong. Đóng bảng điều khiển làm mất kết nối bộ lưu Windows; mở lại và chọn lại thư mục.

## Nhận diện và kiểm thử

Giữ đúng một tab Flow. Kết nối tự đọc mô hình; có thể bấm **Đọc mô hình trên Flow** để đọc lại sau khi thay đổi thủ công. Mục nâng cao có bộ chọn riêng cho số ảnh, lựa chọn số ảnh (`{count}`), nút Download và mục 2K. Nếu DOM chưa nhận diện được, tool dừng và ghi lý do thay vì báo đã áp dụng.

Kiểm thử Node mô phỏng gồm chọn mô hình, đặt/kiểm tra số ảnh, giữ lịch sử mở, lỗi cũ/mới, ba lần hạn mức, nhận đúng download Flow, kiểm tra 1K/2K và luồng tích hợp thành công ngay lần đầu. Python kiểm tra đường dẫn tuyệt đối, ghi file, trùng tên, dữ liệu file tải, định dạng và kích thước 2K.

Các kiểm thử này chưa thay cho kiểm thử đầu-cuối trên tab Flow đăng nhập. Hiện công cụ điều khiển trình duyệt trong phiên chỉ thấy trình duyệt của Codex, không thấy Chrome người dùng. Không thể kết luận đã giải quyết hoàn toàn hiện tượng luôn cần lần hai nếu chưa đối chiếu lịch sử thực tế.

---

## Lịch sử phiên bản — các quy tắc cũ dưới đây không áp dụng cho 0.5.0

### Flow TXT 0.4.0 — Một tab Flow, F5 một lần và ưu tiên mô hình

## Quy tắc mới

- Bấm tiện ích từ bất kỳ tab nào: tự tìm **duy nhất một tab Flow** trong Chrome. Không tự mở thêm tab Flow. Không có tab hoặc có nhiều tab thì báo rõ và yêu cầu giữ một tab; không tự đóng tab người dùng.
- Khi lượt đầu lỗi (kể cả lỗi nhận diện/chuẩn bị hoặc lưu), lưu prompt, cấu hình và lịch sử vào bộ nhớ phiên, F5 đúng tab đó một lần, đợi trang tải rồi khôi phục lần 2. Không tự F5 lần thứ hai trong cùng lượt. Trường hợp đã lưu được ảnh một phần coi là thành công, không F5/tạo lại.
- Sau F5 phải vẫn đúng tab ID và đúng URL dự án. Đổi dự án, đóng tab, nhiều tab Flow, không kết nối được hoặc quá 2 phút sẽ dừng. Nút Dừng hủy khôi phục đang chờ. Không vượt đăng nhập, CAPTCHA, chính sách hoặc hạn mức; thông báo chặn còn tồn tại sau F5 vẫn được xử lý/báo lỗi.
- Nếu lỗi là hạn mức mô hình, rate limit, lỗi tạo hoặc timeout, lần sau F5 ưu tiên mô hình thấp hơn theo danh sách và bỏ qua mô hình đã đánh dấu. Lỗi chính sách giữ nguyên prompt/mô hình. Lỗi lưu cũng có thể dẫn đến tạo lại trong lần 2 theo yêu cầu khôi phục chung; file cũ không bị ghi đè nhưng có thể có ảnh trùng. F5 không hủy công việc trên máy chủ Google, vì vậy timeout/click không rõ kết quả có thể tiêu tốn thêm lượt khi thử lại.
- Bảng **Ưu tiên khi mô hình hết lượt** hiển thị thứ tự, mô hình đang chọn, mô hình bỏ qua và lựa chọn kế tiếp. Pro mặc định bỏ qua theo thông tin người dùng đã xác nhận; Nano Banana 2 rồi Nano Banana 2 Lite là ưu tiên tiếp theo. Bỏ qua không có nghĩa tool biết mô hình còn credit; chỉ phản ánh cấu hình và lịch sử lỗi đã ghi nhận.

Phiên bản này thêm quyền trang `flow.google.com`, `flow.google` và `labs.google/fx` để tìm tab và chèn lại kết nối sau F5. Chrome có thể yêu cầu chấp thuận quyền truy cập mới khi tải lại tiện ích. Giữ bảng điều khiển mở để duy trì quyền ghi thư mục đã chọn. Không có thay đổi file prompt trên máy.

Kiểm thử mô phỏng đã xác nhận checkpoint/khôi phục một lần, không lặp khi nhận nhiều sự kiện tải xong, chặn nhiều tab/đổi dự án và tiếp tục cùng prompt/lịch sử. Chưa xác minh F5 + menu mô hình trên tài khoản Flow thật. Sau cập nhật tiện ích, đóng bảng điều khiển cũ, tải lại Flow và kết nối để thấy **0.4.0**.

Các mục lịch sử phiên bản bên dưới có thể mô tả quy tắc cũ; quy tắc 0.4.0 ở trên được ưu tiên.

Theo yêu cầu người dùng, thông báo chính sách được **thử lại đúng một lần với nguyên prompt và cùng mô hình**, không sửa nội dung hoặc hạ mô hình vì lý do chính sách. Tổng vẫn tối đa hai lần gửi; nếu lần hai tiếp tục bị từ chối thì dừng. Lần hai thành công sẽ hiện trạng thái hoàn tất/ảnh đã lưu, lỗi lần đầu nằm trong lịch sử.

Thông báo chính sách/tạo lỗi đã có trên trang trước khi bắt đầu lượt mới không được dùng để kết luận lượt mới thất bại. Một thông báo mới xuất hiện hoặc thay đổi nội dung vẫn được ghi nhận, kể cả có cùng câu chữ. Lỗi hết credit tài khoản có sẵn vẫn được giữ để ngăn gửi vô ích. Nhận diện này dựa trên DOM; thông báo bị Flow dựng lại hoặc tái sử dụng theo cách khác có thể cần tinh chỉnh.

Bảng kết quả phản ánh **lượt do tool chạy**. Nếu tool đã dừng và bạn tự tạo thủ công trên Flow, ảnh thủ công không được tự gán vào lượt đã kết thúc. Muốn thử lại có theo dõi/lưu ảnh, chạy qua tool.

Cập nhật tiện ích và tab Flow như trước; kiểm tra **0.3.2**. Quy tắc này thay thế các mô tả cũ bên dưới về không thử lại chính sách.

Theo ảnh menu người dùng cung cấp, thứ tự mặc định là **Nano Banana Pro → Nano Banana 2 → Nano Banana 2 Lite**. Bản này mặc định bật **Tạm bỏ qua Pro — đã hết lượt** theo thông tin người dùng xác nhận. Đây là lựa chọn thủ công, không giả lập 3 lần báo hạn mức và không sửa bộ đếm.

Nếu đang chọn Pro, tool sẽ thử chuyển sang Nano Banana 2 trước khi gửi; khi lần đầu thất bại đủ điều kiện thử lại, hạ xuống Nano Banana 2 Lite. Nếu đang chọn Lite thì không tự nâng lên mô hình khác. Khi Pro có lượt trở lại, chọn **Cho phép Pro khi còn lượt**; nếu Pro cũng đã bị bộ đếm tự động đánh dấu 3 lần thì trạng thái tự động vẫn được giữ.

Tải lại tiện ích, đóng bảng điều khiển cũ, F5 Flow và kết nối lại để dùng **0.3.1**. Thứ tự tên đã xác minh từ ảnh; thao tác chuyển menu vẫn cần xác minh trên DOM Flow thực tế. “Pro hết lượt” theo người dùng không chứng minh toàn bộ tài khoản đã hết credit; lỗi hết credit toàn tài khoản vẫn dừng lượt chạy.

## Hành vi hiện tại (thay thế quy tắc thử lại của bản cũ bên dưới)

- Mỗi file vẫn là một prompt. Một lượt có tối đa **2 lần gửi tạo ảnh**: lần đầu và một lần thử lại, cách nhau ít nhất 5 giây, khi Flow báo lỗi tạo, hạn mức mô hình/giới hạn yêu cầu, hoặc hết thời gian chờ mà chưa có ảnh.
- Nếu có 1 trong 4 ảnh thành công, lưu ảnh đó và chấp nhận kết quả một phần. Khi Flow báo lỗi cùng lúc có ảnh thành công, vẫn lưu ảnh. Nếu chỉ thiếu ảnh mà không có thông báo, chờ đến timeout rồi lưu phần đã có.
- Lỗi lưu được thử lại một lần trên chính ảnh đã tạo, không tạo thêm ảnh vì lỗi ổ đĩa/mạng. Vẫn tiếp tục lưu các ảnh còn lại nếu một ảnh lưu thất bại. File có thể có hậu tố nếu lần lưu trước đã tạo file nhưng mất phản hồi.
- Không tự thử lại/đổi mô hình để xử lý vi phạm chính sách hoặc hết credit tài khoản. Lỗi nhận diện thao tác và click không chắc chắn cũng dừng để tránh gửi trùng. Timeout có thể xảy ra khi Flow chưa xử lý xong: thử lại có nguy cơ thêm ảnh/tốn lượt.
- Nếu nhận diện được mô hình, thử chuyển xuống mô hình thấp hơn trước lần gửi thứ hai. Mặc định chỉ hạ tier trong cùng họ/version (Pro/Ultra → thường → Lite/Fast). Điền tên chính xác, mỗi dòng một mô hình trong **Thứ tự mô hình từ cao xuống thấp** để cấu hình thứ tự khác. Chỉ chọn trong các mục thực sự hiện trong menu Flow; xác minh nhãn mô hình sau chuyển rồi mới gửi. Không tìm thấy mô hình thấp hơn thì thử lại cùng mô hình nếu nó chưa bị đánh dấu; menu không nhận diện được thì dừng, không đoán vị trí.
- Sau **3 lần tạo có thông báo hạn mức mô hình**, mô hình được lưu trạng thái **KHÔNG DÙNG**. Chỉ đếm thông báo hạn mức rõ ràng sau khi gửi, không đếm hết credit tài khoản, rate limit chung hoặc việc polling lặp một thông báo. Lần sau nếu đang chọn mô hình bị khóa, tool thử chọn mô hình thấp hơn trước khi tạo; không nhận diện được mô hình thì dừng để tránh dùng nhầm. Đánh dấu lưu qua lần mở Chrome; chưa có tự bỏ đánh dấu khi Google reset quota.
- **Lịch sử gần đây** lưu tối đa 100 lượt trong bộ nhớ cục bộ tiện ích; giao diện hiện 20 lượt gần nhất, gồm thời gian, tên file, tối đa 20.000 ký tự prompt, lần thử, mô hình, thông báo Flow, lỗi hệ thống và file đã lưu. Gỡ tiện ích có thể xóa dữ liệu này. Xuất nhật ký JSON hiện xuất lượt hiện tại; lịch sử nằm trong chrome.storage.local.

Model được đọc từ nút chọn cạnh ô prompt, không dùng API riêng của Google. Chỉ hỗ trợ tên Nano Banana/Imagen hoặc tên được cấu hình rõ ràng. Menu mô hình thay đổi có thể cần chỉnh tích hợp. Kiểm thử mô phỏng đã xác nhận partial 1/4, retry giới hạn, bộ đếm 3 lần, bỏ qua model bị đánh dấu và xác minh chuyển model; chưa kiểm thử menu thật trên tài khoản của bạn.

Để cập nhật: tải lại Flow TXT tại `chrome://extensions`, đóng bảng điều khiển cũ, F5 Flow và kết nối lại; kiểm tra **0.3.0**. Không có quyền mới trong bản này.

Sau khi mở TXT, chỉnh nội dung trong ô **Nội dung prompt**. Nút Tạo ảnh gửi bản đang hiển thị, không sửa file gốc. Có thể nhập trực tiếp nếu chưa chọn TXT. Khi đang chạy, ô sửa được khóa để tránh nhầm nội dung đã gửi.

Khung **Nơi lưu ảnh** hiển thị tên thư mục và vị trí tương đối `thư-mục/run_…/` ngay sau khi chọn; bấm **Đổi thư mục** để chọn nơi khác. Có thể chọn ổ đĩa khác/USB/OneDrive nếu Chrome và Windows cho phép ghi. Không thể hứa truy cập mọi thư mục hệ thống được bảo vệ. Chrome không cung cấp đường dẫn tuyệt đối, nên tool chỉ hiển thị tên thư mục thật nhận được, không tự dựng đường dẫn. Hủy hộp chọn giữ nguyên thư mục trước đó. Nếu dùng Chrome Downloads, khung sẽ ghi rõ chế độ này thay cho thư mục đã chọn.

Tên file đã tồn tại sẽ được thêm `(1)`, `(2)`…; thao tác ghi trong bảng điều khiển được xếp tuần tự, không ghi đè file cũ. Thư mục riêng cho từng lượt cũng giúp tránh trùng tên. Các chương trình bên ngoài đồng thời tạo cùng tên vẫn nằm ngoài khả năng khóa của API trình duyệt.

## Cập nhật

Trong `chrome://extensions`, tải lại Flow TXT, đóng bảng điều khiển cũ, F5 tab Flow rồi kết nối lại. Kiểm tra giao diện hiện phiên bản **0.2.1**. Phiên bản này thay thế cơ chế hàng đợi của 0.1.x; không còn tách dòng, tách `---` hoặc chọn số bắt đầu.

## Sử dụng

1. Mở dự án Flow trong Chrome đang đăng nhập, chọn chế độ ảnh, model và tỉ lệ bạn muốn.
2. Bấm biểu tượng Flow TXT → Kết nối tab Flow này.
3. Chọn **một file TXT** (UTF-8, tối đa 1 MB). Toàn bộ file là một prompt; xuống dòng, đoạn và dòng `---` đều được giữ trong prompt, không tạo thêm lượt gửi.
4. Chọn thư mục lưu một lần cho phiên chạy và cho phép ghi.
5. Chọn số ảnh khớp x1–x4 trên Flow. Bấm **Tạo ảnh**.

Mỗi lượt chỉ gửi một prompt, chờ đủ ảnh rồi lưu. Hoàn tất hoặc lỗi đều kết thúc lượt đó. Bạn có thể chọn file khác và bấm Tạo ảnh để bắt đầu lượt độc lập, không tiếp nối lỗi/hàng đợi cũ. Tool không tự chạy file khác và không tự gửi lại.

Một file vẫn có thể chứa nhiều yêu cầu do người viết nhập: tool không suy đoán để tách chúng. Hãy chuẩn bị một yêu cầu tạo ảnh trong mỗi file.

## Đọc kết quả

- **Trạng thái tool:** đang nhập, đang gửi, chờ ảnh, đang lưu, hoàn tất hoặc cần kiểm tra. Đây là diễn giải của tool.
- **Thông báo từ Google Flow:** nguyên văn thông báo lỗi đọc được trên trang (credit/chính sách/giới hạn), không phải dòng log do tool tự viết. Nếu chưa ghi nhận thì ghi rõ, không coi đó là thành công.
- **Ảnh đã lưu:** tên/đường dẫn file chỉ xuất hiện sau khi thao tác lưu được xác nhận. File đã lưu một phần vẫn hiển thị nếu ảnh sau gặp lỗi.
- **Nhật ký kỹ thuật:** thu gọn mặc định, có nút xuất JSON để chẩn đoán.

Kết quả lượt gần nhất được gắn tên file. Chọn file mới chưa thay thế kết quả cũ; kết quả được làm mới khi bắt đầu lượt mới.

## Lưu ảnh và giới hạn

Mỗi lượt có thư mục `run_…` riêng. Ghi trực tiếp vào thư mục đã chọn không mở Save từng ảnh, không ghi đè file có sẵn. Giữ bảng điều khiển mở; sau khi tải lại bảng phải chọn thư mục lại. Cần đọc được URL ảnh từ Flow, ảnh tối đa 20 MB; nếu bị CORS/quyền truy cập chặn thì dừng và báo lỗi.

Trong cài đặt nâng cao có **Chrome Downloads**. Chế độ này lưu `Downloads/Flow_TXT/run_…`; nếu Chrome hỏi nơi lưu từng ảnh, có thể tắt tùy chọn đó ở `chrome://settings/downloads`. Tool không tự đổi cài đặt Chrome.

Không cấu hình link ảnh gốc thì lưu ảnh đang hiển thị, có thể là preview. Cơ chế nhận diện ảnh vẫn dựa vào DOM/kích thước/URL ảnh mới, chưa hỗ trợ canvas hoặc background-image. Không cuộn trang hay tạo ảnh thủ công trong lúc chạy. Có thể cần điều chỉnh bộ chọn trong phần nâng cao khi Flow đổi giao diện.

## Lỗi và dừng

Hết credit, từ chối chính sách, quá nhiều yêu cầu, timeout hoặc lỗi lưu sẽ dừng lượt hiện tại. Lỗi hệ thống và thông báo Flow hiển thị riêng. Chạy file mới không bị khóa bởi trạng thái lỗi cũ, nhưng hạn mức hoặc thông báo chặn đang còn trên Flow vẫn có thể ngăn lượt mới. Không tự sửa prompt, vượt hạn mức hoặc gửi lại yêu cầu bị từ chối.

Nhận diện lỗi dựa trên thông báo DOM tiếng Việt/Anh. Có thể bỏ sót cách diễn đạt mới hoặc nội dung iframe/canvas; timeout vẫn kết thúc lượt. Dừng không hủy yêu cầu Google đã nhận hoặc tệp Chrome đã bắt đầu tải. Kiểm tra Flow trước khi chạy lại cùng file để tránh tạo trùng.

## Quyền và kiểm thử

Chế độ chuột Chrome dùng quyền `debugger` (đã có từ 0.1.7), chỉ gửi thao tác vào tab Flow và ngắt kết nối sau lần bấm. Đóng DevTools của Flow; Chrome có thể hiện thanh thông báo gỡ lỗi. Không bổ sung quyền ở 0.2.0.

Đã có kiểm thử mô phỏng: một file nhiều dòng gửi đúng một lần, từ chối hàng đợi cũ, chặn bấm chạy trùng, lượt mới chạy được sau lỗi và dữ liệu lỗi Flow cũ được xóa. Các kiểm thử lưu ảnh, phân loại lỗi, thao tác chuột vẫn áp dụng. Giao diện/luồng mới cần xác nhận thực tế trên tài khoản Flow; không tự gửi prompt để kiểm thử trên tài khoản trong quá trình sửa.
