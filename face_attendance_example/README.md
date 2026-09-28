# Face Attendance

Hệ thống nhận diện khuôn mặt điểm danh tự động bằng Python, OpenCV, InsightFace, Flask và SQLite.

## 1. Yêu cầu

- Python 3.11
- Webcam
- Windows/Linux/macOS
- RAM khuyến nghị >= 8 GB

## 2. Tạo môi trường

```bash
python -m venv .venv
```

Windows CMD:

```bash
.venv\Scripts\activate
```

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## 3. Cài thư viện

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Mặc định project dùng CPU để dễ cài đặt.

Nếu muốn dùng GPU NVIDIA, cài bản ONNX Runtime GPU phù hợp với CUDA/cuDNN của máy rồi đặt:

```text
USE_GPU=1
```

## 4. Chạy hệ thống

```bash
python app.py
```

Mở trình duyệt:

```text
http://127.0.0.1:5000
```

Lần đầu InsightFace có thể tải model `buffalo_l` tự động.

## 5. Quy trình demo

1. Vào Sinh viên.
2. Thêm MSSV, họ tên, lớp.
3. Vào Enrollment.
4. Chọn sinh viên.
5. Bật camera.
6. Chụp một ảnh có đúng một khuôn mặt.
7. Hệ thống tạo embedding và lưu vào SQLite.
8. Tạo buổi học bằng API hoặc mở rộng giao diện quản lý session.
9. Vào Điểm danh.
10. Chọn lớp + buổi học.
11. Bật camera.
12. Hệ thống nhận diện và ghi attendance.
13. Vào Lịch sử để tra cứu.

## 6. Test evaluation

Tổ chức:

```text
data/test/
├── 2374802013578/
│   ├── 001.jpg
│   └── 002.jpg
└── 2374802013579/
    ├── 001.jpg
    └── 002.jpg
```

Tên thư mục phải trùng với MSSV trong database.

Sau khi enrollment các sinh viên:

```bash
python evaluation/evaluate.py
```

Kết quả được lưu tại:

```text
evaluation/results.csv
```

## 7. Lưu ý về threshold

`RECOGNITION_THRESHOLD=0.50` chỉ là giá trị khởi đầu cho prototype.

Không được xem 0.50 là ngưỡng tối ưu hay dùng nó làm kết quả đánh giá trong báo cáo nếu chưa thực nghiệm.

Nhóm nên thử nhiều threshold trên validation set và báo cáo threshold được lựa chọn dựa trên dữ liệu thực tế.

## 8. Cấu trúc

```text
face_attendance/
├── app.py
├── config.py
├── requirements.txt
├── database/
├── recognition/
├── routes/
├── templates/
├── static/
├── data/
├── models/
├── database.sqlite
└── evaluation/
```

## 9. Phạm vi hiện tại

Đã có:
- Quản lý sinh viên
- Enrollment
- Face embedding
- Face recognition
- Multi-face recognition
- Attendance
- Chống điểm danh trùng
- Lịch sử
- Chỉnh sửa trạng thái attendance
- Evaluation CSV

Chưa có:
- Liveness detection
- Authentication/role management
- Export Excel
- Dashboard thống kê nâng cao
