# Hệ thống nhận diện khuôn mặt điểm danh tự động

Stack: Python 3.11, Flask, Bootstrap 5, SQLite/SQLAlchemy, OpenCV, DeepFace, RetinaFace, ArcFace pretrained, cosine distance, Flask-Login.

## Cài đặt trên Windows PowerShell

```powershell
cd "D:\Learning\Chuyên đề TN 2\face_attendance"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

Mở http://127.0.0.1:5000/setup, tạo tài khoản quản trị với mật khẩu >= 10 ký tự, sau đó đăng nhập.

Quy trình: Thêm lớp -> Thêm sinh viên -> Upload 3-5 ảnh một người -> Tạo buổi điểm danh -> Mở camera -> Tra cứu/chỉnh sửa kết quả -> Kết thúc buổi.

**Không cần tải SQLite database.** Khi chạy `app.py`, SQLAlchemy tự tạo `instance/attendance.db` và các bảng. Cần tự nhập lớp/sinh viên và ảnh đã có sự đồng ý. Không đưa ảnh, embeddings hoặc DB lên GitHub.

**Trọng số ArcFace/RetinaFace** được DeepFace tải lần đầu, cần Internet. Các bước import/tải model có thể mất thời gian. Không khẳng định tương thích hay hiệu năng trước khi chạy thử trên máy thực tế.

**Ngưỡng:** `FACE_THRESHOLD=0.68` chỉ là ngưỡng khởi tạo để demo, KHÔNG phải ngưỡng đã kiểm định hoặc đảm bảo 80% accuracy. Cần đo trên validation có cả người lạ và điều chỉnh ngưỡng trước khi đánh giá tập test độc lập. Có thể cấu hình trong PowerShell `$env:FACE_THRESHOLD='0.68'` trước khi chạy. Unknown chỉ có nghĩa không vượt ngưỡng; không chứng minh danh tính.

**Giới hạn bản demo:** một khuôn mặt mỗi frame; không có chống ảnh/video giả mạo; không có CSRF protection; không có audit trail chỉnh sửa; chưa có quy trình xóa sinh viên/lớp và migration schema; chưa có đo accuracy; không dùng cho quyết định điểm danh quan trọng khi chưa được giáo viên kiểm tra. Chỉ chạy trên localhost, không public Internet. Camera trình duyệt hoạt động trên localhost hoặc HTTPS. Không sử dụng trên dữ liệu người khác nếu chưa có sự đồng ý phù hợp.

## Cấu trúc
- `app.py`: routes, login, CRUD tạo lớp/sinh viên, đăng ký ảnh, phiên điểm danh, API nhận diện.
- `models.py`: SQLAlchemy models và ràng buộc UNIQUE(session_id,student_id).
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
https://github.com/serengil/deepface — thư viện DeepFace, model ArcFace pretrained, detector RetinaFace. Trọng số không đóng gói trong ZIP. Kiểm tra license của mô hình và bộ dữ liệu trước khi triển khai thực tế.

## Đăng ký bằng webcam
Vào Sinh viên → Đăng ký khuôn mặt → Cách 2: Chụp bằng camera. Chọn Mở camera → Chụp ảnh → Lưu khuôn mặt. Ảnh và embedding được lưu vào hệ thống hiện tại, không cần tạo lại database. Trình duyệt cần quyền camera và truy cập qua localhost hoặc HTTPS.

## Cập nhật logic điểm danh
- Tạo buổi mới: tự tạo bản ghi `absent` cho từng sinh viên trong lớp, thời gian hiển thị `—` khi Vắng.
- Nhận diện thành công: đổi `absent` thành `present`, ghi thời gian; không ghi đè `present` hoặc `late`.
- Sắp xếp: Có mặt -> Đi muộn -> Vắng; trong nhóm theo tên gọi, tên đệm, họ (A-Z, bỏ dấu để so sánh).
- Chỉnh sửa thủ công sang Vắng: ẩn thời gian điểm danh trong giao diện.
- Database SQLite cũ vẫn được giữ. Với các buổi tạo từ phiên bản cũ, sinh viên chưa có bản ghi sẽ hiển thị là Vắng; bản ghi sẽ được tạo khi thao tác chỉnh sửa hoặc nhận diện.
- Giữ nguyên schema cũ (`recorded_at` NOT NULL) để tương thích SQLite hiện tại. Với trạng thái Vắng, timestamp nội bộ không phải thời gian có mặt và không được hiển thị.
