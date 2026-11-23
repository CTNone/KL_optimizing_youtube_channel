# Phiếu thực nghiệm khóa luận

## 1. Mục đích

Đánh giá khả năng quản trị và truy vết quy trình của Content Hub. Phiếu này không đo
hiệu quả kinh doanh của kênh và không dùng lượt xem/doanh thu để kết luận hệ thống làm
tăng trưởng YouTube.

Chỉ điền số sau khi thực hiện. Không lấy số minh họa trong database demo làm kết quả
thực nghiệm.

## 2. Thông tin lần chạy

| Trường | Giá trị |
|---|---|
| Mã lần chạy |  |
| Ngày/giờ, múi giờ |  |
| Người thực hiện |  |
| Phiên bản/commit của Hub |  |
| Cách chạy | Source / EXE |
| Máy, CPU, RAM, ổ lưu trữ |  |
| Windows/Python |  |
| Database và bộ dữ liệu |  |
| Ghi chú điều kiện khác |  |

## 3. Nguyên tắc so sánh

- Dùng cùng một bộ brief, file nguồn và kịch bản cho quy trình hiện tại và Hub.
- Dùng cùng người thực hiện và máy tính nếu có thể; nếu khác, ghi rõ khác biệt.
- Đo riêng **thời gian thao tác chủ động** và **thời gian chờ máy/dịch vụ**. Không cộng
  thời gian chờ YouTube xử lý báo cáo vào thời gian thao tác quản trị.
- Ghi mọi lần làm lại, lỗi và lần chuyển công cụ; không bỏ lượt thất bại khỏi mẫu.
- Giữ dữ liệu thử nghiệm tách database sản xuất. Phân biệt dữ liệu tổng hợp với dữ liệu
  thật trong ảnh chụp, log và báo cáo.

## 4. Bảng đo quy trình

Mỗi hàng là một lượt thực hiện một tác vụ bằng một phương pháp.

| Lượt | Tác vụ | Phương pháp (thủ công/Hub) | Bắt đầu | Kết thúc | Thao tác chủ động (giây) | Chờ máy/dịch vụ (giây) | Chuyển công cụ | Lỗi/làm lại | Gắn nhầm tài nguyên | Hoàn tất? | Bằng chứng |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|
|  | Tìm trạng thái và đúng nguồn của video |  |  |  |  |  |  |  |  |  |  |
|  | Bàn giao video sang bước sản xuất |  |  |  |  |  |  |  |  |  |  |
|  | QC bản thành phẩm và xác nhận phiên bản |  |  |  |  |  |  |  |  |  |  |
|  | Nhập link/ngày đăng và làm mới Analytics |  |  |  |  |  |  |  |  |  |  |

## 5. Kiểm tra tính đúng đắn và phục hồi

| ID | Kịch bản | Kết quả mong đợi | Kết quả quan sát | Đạt? | Log/ảnh/hồ sơ liên quan |
|---|---|---|---|---|---|
| V1 | Tạo video gắn vào album thuộc cùng kênh | Video hiện dưới đúng kênh và album |  |  |  |
| V2 | Thử chuyển bước khi thiếu brief/tài nguyên bắt buộc | Từ chối chuyển; trạng thái và audit không đổi dở dang |  |  |  |
| V3 | Thay file thành phẩm sau khi QC duyệt | QC cũ không còn hợp lệ; cần duyệt lại |  |  |  |
| V4 | Đổi Bước bằng menu chuột phải | Ghi audit `manual`/`override`; gate tuần tự không bị ảnh hưởng |  |  |  |
| V5 | Kết nối/ngắt một kênh trong Analytics | Token/snapshot chỉ thuộc kênh đó; kênh khác giữ nguyên |  |  |  |
| V6 | Làm mới video/kênh bằng tài khoản thật | Dùng đúng `channel==id`, đúng ngày đăng; CTR trễ được báo rõ |  |  |  |
| V7 | Sao lưu database demo và đối chiếu hồ sơ xuất | Dữ liệu chính/asset/QC/audit khớp phạm vi đã xuất |  |  |  |

Ghi chú khi một ca không đạt:

```text
ID ca:
Các bước tái hiện:
Kết quả thực tế:
Thông báo/log:
Ảnh hoặc tệp bằng chứng:
Lỗi sản phẩm hay lỗi môi trường:
```

## 6. Tính toán sau khi thu thập

- Trung vị thời gian thao tác cho mỗi phương pháp và tác vụ.
- Số lần chuyển công cụ, lỗi và gắn nhầm tài nguyên trên số lượt đã chạy.
- Tỷ lệ hoàn thành: `lượt hoàn tất / tổng lượt thực hiện`.
- Mức thay đổi thời gian thao tác: `(T_thủ_công - T_Hub) / T_thủ_công × 100%`.

Chỉ tính tỷ lệ khi dữ liệu hai phương pháp có cùng tác vụ và điều kiện so sánh. Báo cáo
số lượt, cách lấy mẫu, ngoại lệ và thời gian chờ riêng; không suy rộng quá tập thử nghiệm.

## 7. Tóm tắt kết quả — chỉ điền sau thực nghiệm

```text
Số kênh / album / video đã thử:
Số lượt theo từng phương pháp:
Trung vị thời gian thao tác thủ công:
Trung vị thời gian thao tác Hub:
Thời gian chờ báo cáo/dịch vụ riêng:
Số lần chuyển công cụ:
Số lỗi / số lần làm lại:
Số trường hợp gắn nhầm tài nguyên:
Các ca phục hồi đạt / tổng số ca:
Những giới hạn làm ảnh hưởng phép so sánh:
```

## 8. Bằng chứng cần lưu

- Mã/phiên bản phần mềm và cấu hình máy.
- Cùng bộ dữ liệu đầu vào cho hai phương pháp.
- Bảng ghi lượt chạy, log/ảnh chụp thao tác, hồ sơ JSON đã xuất và snapshot Analytics.
- Database demo trước/sau nếu cần chứng minh trạng thái; không đưa database sản xuất
  hoặc thông tin tài khoản vào phụ lục công khai.
- Ghi rõ ca nào dùng dữ liệu tổng hợp, ca nào dùng dữ liệu thật đã được phép sử dụng.
