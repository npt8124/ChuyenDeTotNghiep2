# Hệ thống nhận diện khuôn mặt điểm danh tự động

Stack: Python 3.11, Flask, Bootstrap 5, SQLite/SQLAlchemy, OpenCV, DeepFace, RetinaFace, ArcFace pretrained, cosine distance, Flask-Login.

## Cài đặt trên Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Mở http://127.0.0.1:5000/setup để tạo tài khoản quản trị ban đầu với mật khẩu >= 10 ký tự. Tài khoản giảng viên đăng ký ở nút **Đăng ký bằng key** trên trang đăng nhập; key demo mặc định là `vanlanguniteacher`. Có thể đặt key khác trước khi chạy:

```powershell
$env:TEACHER_REGISTRATION_KEY='mot-key-rieng-va-kho-doan'
python app.py
```

Tài khoản tạo bằng key luôn có vai trò giảng viên; chỉ tài khoản quản trị/giảng viên đăng nhập được. Sinh viên không cần tạo tài khoản: trang chủ công khai hiển thị các buổi đang mở và cho phép vào camera điểm danh. Danh sách sinh viên, lịch sử và ảnh điểm danh chỉ dành cho tài khoản nhân viên.

Quy trình: Thêm lớp -> Thêm sinh viên -> Upload 3-5 ảnh một người -> Tạo buổi điểm danh -> Mở camera -> Tra cứu/chỉnh sửa kết quả -> Kết thúc buổi.

**Không cần tải SQLite database.** Khi chạy `app.py`, SQLAlchemy tự tạo `instance/attendance.db` và các bảng. Cần tự nhập lớp/sinh viên và ảnh đã có sự đồng ý. Không đưa ảnh, embeddings hoặc DB lên GitHub.

**Trọng số ArcFace/RetinaFace** được DeepFace tải lần đầu, cần Internet. Các bước import/tải model có thể mất thời gian. Không khẳng định tương thích hay hiệu năng trước khi chạy thử trên máy thực tế.

**Ngưỡng:** `FACE_THRESHOLD=0.68` chỉ là ngưỡng khởi tạo để demo, KHÔNG phải ngưỡng đã kiểm định hoặc đảm bảo 80% accuracy. Cần đo trên validation có cả người lạ và điều chỉnh ngưỡng trước khi đánh giá tập test độc lập. Có thể cấu hình trong PowerShell `$env:FACE_THRESHOLD='0.68'` trước khi chạy. Unknown chỉ có nghĩa không vượt ngưỡng; không chứng minh danh tính.

**Giới hạn bản demo:** một khuôn mặt mỗi frame; không có chống ảnh/video giả mạo đáng tin cậy; không có CSRF protection, giới hạn thử đăng nhập hay audit trail chỉnh sửa; chưa có đo accuracy; không dùng cho quyết định điểm danh quan trọng khi chưa được giáo viên kiểm tra. Dù đã mở quyền khách để tham gia điểm danh, ứng dụng hiện chưa được gia cố để public Internet. Trước khi deploy cần dùng HTTPS, thay `SECRET_KEY` và `TEACHER_REGISTRATION_KEY` bằng giá trị mạnh, bảo vệ/tách quyền lưu database và ảnh, bổ sung CSRF/rate-limit/backup và quy trình đồng ý, lưu giữ, xóa dữ liệu khuôn mặt. Camera trình duyệt hoạt động trên localhost hoặc HTTPS. Không sử dụng trên dữ liệu người khác nếu chưa có sự đồng ý phù hợp.

## Cấu trúc
- `app.py`: routes, login, CRUD tạo lớp/sinh viên, đăng ký ảnh, phiên điểm danh, API nhận diện.
- `models.py`: SQLAlchemy models và ràng buộc UNIQUE(session_id,student_id); ảnh camera điểm danh lưu dạng PNG BLOB trong `attendance`.
- `recognition.py`: DeepFace embeddings, cosine matching theo lớp.
- `config.py`: cấu hình.
- `templates/`, `static/`: giao diện Bootstrap và webcam JavaScript.
- `instance/`: database tự sinh.
- `uploads/faces/`: ảnh đăng ký (không commit).

## Kiểm thử
1. Hai ảnh của cùng người được đăng ký, thử điểm danh -> present.
2. Người xuất hiện lần hai -> already_recorded.
3. Người lạ -> unknown nếu vượt ngưỡng (cần hiệu chỉnh để kiểm soát nhận nhầm).
4. Hai khuôn mặt cùng khung -> multiple_faces.
5. Kết thúc buổi -> API không nhận điểm danh mới.
6. Kiểm tra sửa thủ công trạng thái có mặt/đi muộn/vắng.
7. Đánh giá độc lập tỷ lệ nhận diện đúng, false acceptance, false rejection, latency.

## Nguồn mô hình
https://github.com/serengil/deepface — thư viện DeepFace, model ArcFace pretrained, detector RetinaFace. 

## Đăng ký bằng webcam
Vào Sinh viên → Đăng ký khuôn mặt → Cách 2: Chụp bằng camera. Chọn Mở camera → Chụp ảnh → Lưu khuôn mặt. Ảnh và embedding được lưu vào hệ thống hiện tại, không cần tạo lại database. Trình duyệt cần quyền camera và truy cập qua localhost hoặc HTTPS.

## Cập nhật logic điểm danh
- Tạo buổi mới: tự tạo bản ghi `absent` cho từng sinh viên trong lớp, thời gian hiển thị `—` khi Vắng.
- Nhận diện thành công: đổi `absent` thành `present`, ghi thời gian; không ghi đè `present` hoặc `late`.
- Sắp xếp: Có mặt -> Đi muộn -> Vắng; trong nhóm theo tên gọi, tên đệm, họ (A-Z, bỏ dấu để so sánh).
- Chỉnh sửa thủ công sang Vắng: ẩn thời gian điểm danh trong giao diện.
- Database SQLite cũ vẫn được giữ. Khi khởi động, migration bổ sung vai trò (tài khoản cũ chuyển thành quản trị viên), `match_distance` và ảnh BLOB. Với các buổi tạo từ phiên bản cũ, sinh viên chưa có bản ghi sẽ hiển thị là Vắng; bản ghi sẽ được tạo khi thao tác chỉnh sửa hoặc nhận diện.
- Giữ nguyên schema cũ (`recorded_at` NOT NULL) để tương thích SQLite hiện tại. Với trạng thái Vắng, timestamp nội bộ không phải thời gian có mặt và không được hiển thị.


## Các chức năng bổ sung
- Import sinh viên: hỗ trợ `.xlsx` và `.csv`, tiêu đề cột `MSSV` và `Họ tên`; chọn lớp trên giao diện; có bước xem trước và bỏ qua dòng lỗi/MSSV trùng.
- Điểm danh: lưu `match_distance` cho lần nhận diện tự động; giao diện hiển thị điểm tương đồng quy đổi `(1 - cosine_distance) × 100`. Đây là điểm tương đồng, KHÔNG phải xác suất nhận diện đúng. Database cũ được bổ sung cột bằng migration SQLite khi khởi động, không xóa dữ liệu.
- Khi ghi nhận một lần điểm danh tự động mới, ảnh frame tương ứng được mã hóa PNG và lưu trực tiếp trong cột BLOB của database. Ảnh không được thay bằng các frame nhận diện lặp lại; thao tác sửa thủ công xóa ảnh/điểm tương đồng để không gắn nhầm ảnh nhận diện vào kết quả thủ công. Dữ liệu ảnh làm database tăng nhanh, nên cần chính sách lưu trữ/xóa phù hợp.
- Camera xin độ phân giải ưu tiên 1280×720 và gửi ảnh JPEG chất lượng cao hơn; thiết bị/trình duyệt có thể trả về độ phân giải thấp hơn. Chất lượng còn phụ thuộc camera, ánh sáng, khoảng cách và dữ liệu đăng ký; tăng độ phân giải không đảm bảo tăng độ chính xác.
- Anti-Spoofing: chỉ bật trong API điểm danh camera realtime qua `DeepFace.extract_faces(..., anti_spoofing=True)` (FasNet). Hai cách đăng ký khuôn mặt upload ảnh và chụp camera vẫn giữ nguyên, không chạy kiểm tra anti-spoofing. Lần đầu có thể cần tải trọng số FasNet. Cần kiểm thử thực tế; không bảo đảm phát hiện mọi kiểu giả mạo.
- Cài dependency mới: `python -m pip install -r requirements.txt`.
