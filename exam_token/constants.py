ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'quan_ly_thi'
ROLE_PROCTOR = 'can_bo_coi_thi'
ROLE_MARKER = 'can_bo_cham_diem'
ROLE_MARKER_1 = 'giam_khao_1'
ROLE_MARKER_2 = 'giam_khao_2'
ROLE_VIEWER = 'viewer'

ROLE_CHOICES = [
    (ROLE_ADMIN, 'Admin'),
    (ROLE_MANAGER, 'Quản lý thi'),
    (ROLE_PROCTOR, 'Cán bộ coi thi'),   
    (ROLE_MARKER_1, 'Giám khảo 1'),
    (ROLE_MARKER_2, 'Giám khảo 2'),
    (ROLE_VIEWER, 'Viewer'),
]

SESSION_OPEN = 'dang_mo'
SESSION_RUNNING = 'dang_lam_bai'
SESSION_COLLECTED = 'da_thu'
SESSION_FINISHED = 'hoan_thanh'
SESSION_CANCELED = 'huy'

SESSION_STATUS_CHOICES = [
    (SESSION_OPEN, 'Đang mở'),
    (SESSION_RUNNING, 'Đang làm bài'),
    (SESSION_COLLECTED, 'Đã thu bài'),
    (SESSION_FINISHED, 'Hoàn thành'),
    (SESSION_CANCELED, 'Hủy'),
]

QR_UNUSED = 'chua_gan'
QR_ASSIGNED = 'da_gan'
QR_COLLECTED = 'da_thu'
QR_CANCELED = 'huy'

QR_STATUS_CHOICES = [
    (QR_UNUSED, 'Chưa gán'),
    (QR_ASSIGNED, 'Đã gán'),
    (QR_COLLECTED, 'Đã thu'),
    (QR_CANCELED, 'Hủy'),
]

ASSIGN_ASSIGNED = 'da_gan'
ASSIGN_COLLECTED = 'da_thu'
ASSIGN_CANCELED = 'huy'

ASSIGN_STATUS_CHOICES = [
    (ASSIGN_ASSIGNED, 'Đã gán'),
    (ASSIGN_COLLECTED, 'Đã thu'),
    (ASSIGN_CANCELED, 'Hủy'),
]

ACTIVE_STAFF = 'dang_lam_viec'
INACTIVE_STAFF = 'nghi_cong_tac'
STAFF_STATUS_CHOICES = [
    (ACTIVE_STAFF, 'Đang làm việc'),
    (INACTIVE_STAFF, 'Nghỉ công tác'),
]

EXAM_MINUTE_CHOICES = [(90, '90 phút'), (120, '120 phút'), (150, '150 phút'), (180, '180 phút')]
LATE_ASSIGN_GRACE_MINUTES = 15