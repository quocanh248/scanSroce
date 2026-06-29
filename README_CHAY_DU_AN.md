# Hệ thống chấm điểm trực tuyến - Django + TailwindCSS + MySQL

Source này là bản viết mới toàn bộ theo yêu cầu:

- Django + MySQL.
- Giao diện xanh/trắng theo phong cách màn hình mẫu.
- Quản lý cán bộ, user, phân quyền bằng Django Group.
- Import thí sinh Excel/CSV.
- Quản lý đợt in QR, trạng thái QR: `chua_gan`, `da_gan`, `da_thu`, `huy`.
- Tạo phiên thi, thời gian làm bài 60/90/120/150/180 phút.
- Gán QR, tính giờ, đếm ngược, tự thu bài khi hết giờ.
- Sau khi thu bài: khóa ô gán dữ liệu, chỉ cho hủy bài và in biên bản.
- Hoàn thành phiên thi: khóa toàn bộ, ghi log, đăng xuất.
- In biên bản giao nộp PDF theo mẫu, tự phân trang.
- Phiếu chấm điểm chi tiết theo giao diện ảnh mẫu.
- Log toàn bộ thao tác trong phiên thi.

## 1. Chuẩn bị database

Khuyến nghị tạo DB mới hoặc backup DB cũ trước khi chạy bản mới.

```bat
mysql -u root1 -p -e "CREATE DATABASE IF NOT EXISTS quan_ly_diem_scan_token CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## 2. Tạo môi trường Python

```bat
cd C:\VB2-T05\DTHS2-T05\TIN HỌC\SCORE\scan_score_full_source
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Nếu dùng Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Cấu hình `.env`

Copy file mẫu:

```bat
copy .env.example .env
```

Mở `.env` và sửa:

```env
DB_NAME=quan_ly_diem_scan_token
DB_USER=root1
DB_PASSWORD=mat_khau_mysql_cua_ban
DB_HOST=127.0.0.1
DB_PORT=3306
```

Font PDF tiếng Việt trên Windows:

```env
VIETNAMESE_PDF_FONT_PATH=C:\Windows\Fonts\times.ttf
VIETNAMESE_PDF_BOLD_FONT_PATH=C:\Windows\Fonts\timesbd.ttf
```

## 4. Tạo bảng Django

```bat
python manage.py makemigrations exam_token
python manage.py migrate
python manage.py bootstrap_exam_roles
python manage.py createsuperuser
```

Có thể tạo dữ liệu mẫu để test nhanh:

```bat
python manage.py seed_demo
```

Tài khoản mẫu nếu chạy `seed_demo`:

- `admin / 12345678`
- `coithi / 12345678`

## 5. Chạy server

```bat
python manage.py runserver
```

Mở trình duyệt:

```text
http://127.0.0.1:8000/dang-nhap/
```

## 6. Luồng kiểm thử nhanh

1. Đăng nhập admin.
2. Vào **Người dùng** tạo cán bộ và gán group.
3. Vào **Quản lý QR** tạo đợt in QR, in PDF QR.
4. Vào **Import thí sinh** nạp danh sách lớp.
5. Vào **Tạo phiên thi**, chọn thời gian làm bài.
6. Vào **Gán QR**, quét QR + SBD.
7. Bấm **Tính giờ làm bài** để chạy countdown.
8. Hết giờ hệ thống tự thu bài, hoặc bấm **Thu bài**.
9. Sau thu bài chỉ được hủy bài và in biên bản.
10. Bấm **Hoàn thành việc coi thi** để khóa phiên và đăng xuất.

## 7. Nhóm quyền

- `admin`: full quyền, tạo user.
- `quan_ly_thi`: import thí sinh, quản lý QR, tạo phiên thi, gán QR, thu bài, hủy bài, in biên bản.
- `can_bo_coi_thi`: tạo phiên thi, gán QR, thu bài, hủy bài, in biên bản.
- `can_bo_cham_diem`: xem/chấm bài thi.
- `viewer`: xem dashboard/lịch sử.

## 8. File quan trọng

- `scan_score/settings.py`: cấu hình database, font PDF, static/media.
- `exam_token/models.py`: toàn bộ bảng nghiệp vụ.
- `exam_token/services.py`: nghiệp vụ gán QR, thu bài, hủy bài, log.
- `exam_token/views.py`: toàn bộ màn hình.
- `exam_token/templates/exam_token/base.html`: layout xanh/trắng theo ảnh mẫu.
- `exam_token/templates/exam_token/score_detail.html`: phiếu chấm điểm chi tiết theo ảnh mẫu.
