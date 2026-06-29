from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.conf import settings

from .constants import (
    ACTIVE_STAFF,
    ASSIGN_ASSIGNED,
    ASSIGN_STATUS_CHOICES,
    EXAM_MINUTE_CHOICES,
    QR_STATUS_CHOICES,
    QR_UNUSED,
    SESSION_OPEN,
    SESSION_STATUS_CHOICES,
    STAFF_STATUS_CHOICES,
)


class Lop(models.Model):
    ma_lop = models.CharField(max_length=50, primary_key=True)
    ten_lop = models.CharField(max_length=255)
    ghi_chu = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'lop'
        verbose_name = 'Lớp'
        verbose_name_plural = 'Lớp'

    def __str__(self):
        return f'{self.ma_lop} - {self.ten_lop}'


class MonHoc(models.Model):
    ma_mon = models.CharField(max_length=50, primary_key=True)
    ten_mon = models.CharField(max_length=255)

    class Meta:
        db_table = 'mon_hoc'
        verbose_name = 'Môn học'
        verbose_name_plural = 'Môn học'

    def __str__(self):
        return f'{self.ma_mon} - {self.ten_mon}'


class HocVien(models.Model):
    ma_hoc_vien = models.CharField(max_length=50, primary_key=True)
    so_bao_danh = models.IntegerField(null=True, blank=True)
    ho_ten = models.CharField(max_length=255)
    ngay_sinh = models.DateField(null=True, blank=True)
    gioi_tinh = models.CharField(max_length=20, blank=True, null=True)
    lop = models.ForeignKey(Lop, db_column='ma_lop', to_field='ma_lop', on_delete=models.PROTECT, related_name='hoc_viens')
    trang_thai = models.CharField(max_length=50, default='dang_hoc')

    class Meta:
        db_table = 'hoc_vien'
        indexes = [models.Index(fields=['lop', 'so_bao_danh'])]
        verbose_name = 'Học viên'
        verbose_name_plural = 'Học viên'

    def __str__(self):
        return f'{self.so_bao_danh or ""} - {self.ho_ten}'


class CanBo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='can_bo')
    ma_can_bo = models.CharField(max_length=50, unique=True)
    ten_can_bo = models.CharField(max_length=255)
    ngay_sinh = models.DateField(null=True, blank=True)
    gioi_tinh = models.CharField(max_length=20, blank=True, null=True)
    cap_bac = models.CharField(max_length=100, blank=True, null=True)
    chuc_vu = models.CharField(max_length=150, blank=True, null=True)
    don_vi = models.CharField(max_length=255, blank=True, null=True)
    sdt = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    trang_thai = models.CharField(max_length=50, choices=STAFF_STATUS_CHOICES, default=ACTIVE_STAFF)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'can_bo'
        verbose_name = 'Cán bộ'
        verbose_name_plural = 'Cán bộ'

    def __str__(self):
        return f'{self.ma_can_bo} - {self.ten_can_bo}'


class PhienThi(models.Model):
    ma_phien_thi = models.CharField(max_length=150, unique=True)
    mon = models.ForeignKey(MonHoc, db_column='ma_mon', to_field='ma_mon', on_delete=models.PROTECT, related_name='phien_this')
    lop = models.ForeignKey(Lop, db_column='ma_lop', to_field='ma_lop', on_delete=models.PROTECT, related_name='phien_this')
    can_bo_coi_thi_1 = models.CharField(max_length=150, blank=True)
    can_bo_coi_thi_2 = models.CharField(max_length=150, blank=True)
    ten_ky_thi = models.CharField(max_length=255, default='Kiểm tra')   
    thoi_gian_lam_bai = models.PositiveIntegerField(choices=EXAM_MINUTE_CHOICES, default=90)
    ngay_thi = models.DateField()
    phong_thi = models.CharField(max_length=100)    
    trang_thai = models.CharField(max_length=50, choices=SESSION_STATUS_CHOICES, default=SESSION_OPEN)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_sessions')
    ghi_chu = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'phien_thi'
        indexes = [models.Index(fields=['lop']), models.Index(fields=['trang_thai'])]
        verbose_name = 'Phiên thi'
        verbose_name_plural = 'Phiên thi'

    def __str__(self):
        return self.ma_phien_thi

    @property
    def is_time_locked(self):
        return bool(self.started_at)

    @property
    def is_finished(self):
        return self.trang_thai == 'hoan_thanh'


class QRBatch(models.Model):
    ma_dot = models.CharField(max_length=80, unique=True)
    so_luong = models.PositiveIntegerField(default=0)
    ngay_in = models.DateField(blank=True, null=True)
    ngay_in_prefix = models.CharField(max_length=10, blank=True, null=True)
    noi_dung_bat_dau = models.CharField(max_length=150, blank=True, null=True, default="DHCSND_000001",)
    noi_dung_ket_thuc = models.CharField(max_length=150, blank=True, null=True)
    trang_thai = models.CharField(max_length=50, default='dang_su_dung')
    printed_pdf_path = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'qr_batch'
        verbose_name = 'Đợt in QR'
        verbose_name_plural = 'Đợt in QR'

    def __str__(self):
        return self.ma_dot


class QRTokenBaiThi(models.Model):
    batch = models.ForeignKey(QRBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='tokens')
    token = models.CharField(max_length=500, unique=True)
    noi_dung = models.CharField(max_length=150, blank=True, null=True)
    token_ma_hoa = models.CharField(max_length=500, blank=True, null=True)
    public_token = models.CharField(max_length=500, blank=True, null=True)
    qr_link = models.CharField(max_length=500, blank=True, null=True)
    ngay_in_prefix = models.CharField(max_length=10, blank=True, null=True)
    trang_thai = models.CharField(max_length=50, choices=QR_STATUS_CHOICES, default=QR_UNUSED)
    printed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    ghi_chu = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'qr_token_bai_thi'
        indexes = [models.Index(fields=['trang_thai']), models.Index(fields=['batch'])]
        verbose_name = 'QR bài thi'
        verbose_name_plural = 'QR bài thi'

    def __str__(self):
        return self.token


class GanTokenBaiThi(models.Model):
    token = models.ForeignKey(QRTokenBaiThi, on_delete=models.PROTECT, related_name='assignments')
    phien_thi = models.ForeignKey(PhienThi, on_delete=models.PROTECT, related_name='assignments')
    hoc_vien = models.ForeignKey(HocVien, db_column='ma_hoc_vien', to_field='ma_hoc_vien', on_delete=models.PROTECT, related_name='assignments')
    so_to = models.PositiveIntegerField(default=1)
    trang_thai = models.CharField(max_length=50, choices=ASSIGN_STATUS_CHOICES, default=ASSIGN_ASSIGNED)
    ghi_chu = models.TextField(blank=True, null=True)
    ly_do_huy = models.TextField(blank=True, null=True)
    thoi_gian_gan = models.DateTimeField(default=timezone.now)
    thoi_gian_thu = models.DateTimeField(null=True, blank=True)
    thoi_gian_huy = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'gan_token_bai_thi'
        indexes = [models.Index(fields=['phien_thi', 'hoc_vien', 'trang_thai'])]
        verbose_name = 'Gán QR bài thi'
        verbose_name_plural = 'Gán QR bài thi'

    def __str__(self):
        return f'{self.phien_thi} - {self.hoc_vien} - Tờ {self.so_to}'


class ExamSessionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    can_bo = models.ForeignKey(CanBo, on_delete=models.SET_NULL, null=True, blank=True)
    phien_thi = models.ForeignKey(PhienThi, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'exam_session_log'
        indexes = [models.Index(fields=['phien_thi', 'created_at']), models.Index(fields=['action'])]
        verbose_name = 'Log phiên thi'
        verbose_name_plural = 'Log phiên thi'

    def __str__(self):
        return f'{self.created_at:%d/%m/%Y %H:%M} - {self.action}'


class BaiThiScanDiem(models.Model):
    token = models.ForeignKey(QRTokenBaiThi, on_delete=models.SET_NULL, null=True, blank=True)
    token_text = models.CharField(max_length=120, blank=True, null=True)
    phien_thi = models.ForeignKey(PhienThi, on_delete=models.SET_NULL, null=True, blank=True)
    gan_token = models.ForeignKey(GanTokenBaiThi, on_delete=models.SET_NULL, null=True, blank=True)
    hoc_vien = models.ForeignKey(HocVien, db_column='ma_hoc_vien', to_field='ma_hoc_vien', on_delete=models.SET_NULL, null=True, blank=True)
    nguoi_cham = models.ForeignKey(CanBo, on_delete=models.SET_NULL, null=True, blank=True, related_name='bai_cham')
    image_path = models.CharField(max_length=500, blank=True, null=True)
    diem_nhan_dien = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    diem_chot = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    nhan_xet = models.TextField(blank=True, null=True)
    trang_thai = models.CharField(max_length=50, default='cho_cham')
    raw_result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    thoi_gian_chot = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bai_thi_scan_diem'
        indexes = [models.Index(fields=['trang_thai']), models.Index(fields=['token_text'])]
        verbose_name = 'Bài thi scan điểm'
        verbose_name_plural = 'Bài thi scan điểm'

    def __str__(self):
        return self.token_text or f'Bài scan {self.pk}'


class ChamDiemChiTiet(models.Model):
    bai_thi = models.ForeignKey(BaiThiScanDiem, on_delete=models.CASCADE, related_name='chi_tiet')
    cau_so = models.PositiveIntegerField()
    noi_dung = models.CharField(max_length=255)
    diem_toi_da = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    diem_dat = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ghi_chu = models.TextField(blank=True, null=True)
    image_path = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'cham_diem_chi_tiet'
        ordering = ['cau_so']
        verbose_name = 'Chấm điểm chi tiết'
        verbose_name_plural = 'Chấm điểm chi tiết'

    def __str__(self):
        return f'{self.bai_thi_id} - Câu {self.cau_so}'

class ChamDiemBaiThi(models.Model):
    TRANG_THAI_CHOICES = [
        ("chua_cham", "Chưa chấm"),
        ("da_cham_gk1", "Đã chấm GK1"),
        ("da_cham_gk2", "Đã chấm GK2"),
        ("da_doi_chieu", "Đã đối chiếu"),
        ("chua_thong_nhat", "Chưa thống nhất"),
        ("can_cham_thong_nhat", "Cần chấm thống nhất"),
        ("cho_truong_hoi_dong", "Chờ Trưởng hội đồng"),
        ("hoan_tat", "Hoàn tất"),
    ]

    gan_token = models.OneToOneField(
        "GanTokenBaiThi",
        on_delete=models.CASCADE,
        related_name="cham_diem",
    )
    phien_thi = models.ForeignKey(
        "PhienThi",
        on_delete=models.CASCADE,
        related_name="bai_cham_diem",
    )
    token = models.ForeignKey(
        "QRTokenBaiThi",
        on_delete=models.PROTECT,
        related_name="bai_cham_diem",
    )
    diem_chinh_thuc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    do_lech = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    trang_thai = models.CharField(max_length=30, choices=TRANG_THAI_CHOICES, default="chua_cham")
    ghi_chu = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cham_diem_bai_thi"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Bài chấm #{self.pk} - {self.trang_thai}"


class PhieuCham(models.Model):
    LAN_CHAM_CHOICES = [
        (1, "Giám khảo 1"),
        (2, "Giám khảo 2"),
        (3, "Phiếu thống nhất"),
    ]
    TRANG_THAI_CHOICES = [
        ("dang_cham", "Đang chấm"),
        ("da_nop", "Đã nộp"),
        ("huy", "Hủy"),
    ]

    bai_cham = models.ForeignKey(
        ChamDiemBaiThi,
        on_delete=models.CASCADE,
        related_name="phieu_cham",
    )
    lan_cham = models.PositiveSmallIntegerField(choices=LAN_CHAM_CHOICES)
    nguoi_cham = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="phieu_cham",
    )
    tong_diem = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default="da_nop")
    ghi_chu = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "phieu_cham"
        constraints = [
            models.UniqueConstraint(
                fields=["bai_cham", "lan_cham"],
                condition=models.Q(trang_thai="da_nop"),
                name="uniq_bai_lan_cham_da_nop",
            )
        ]
        ordering = ["bai_cham_id", "lan_cham"]

    def __str__(self):
        return f"Phiếu chấm {self.lan_cham} - {self.tong_diem}"


class PhieuChamChiTiet(models.Model):
    phieu_cham = models.ForeignKey(
        PhieuCham,
        on_delete=models.CASCADE,
        related_name="chi_tiet",
    )
    cau_so = models.PositiveSmallIntegerField()
    diem = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = "phieu_cham_chi_tiet"
        ordering = ["cau_so"]
        constraints = [
            models.UniqueConstraint(fields=["phieu_cham", "cau_so"], name="uniq_phieu_cau_so")
        ]


class DoiChieuChamDiem(models.Model):
    KET_QUA_CHOICES = [
        ("hop_le_tu_dong", "Hợp lệ tự động"),
        ("chua_thong_nhat", "Chưa thống nhất"),
        ("cho_truong_hoi_dong", "Chờ Trưởng hội đồng"),
    ]

    bai_cham = models.ForeignKey(
        ChamDiemBaiThi,
        on_delete=models.CASCADE,
        related_name="doi_chieu",
    )
    phieu_gk1 = models.ForeignKey(
        PhieuCham,
        on_delete=models.PROTECT,
        related_name="doi_chieu_gk1",
    )
    phieu_gk2 = models.ForeignKey(
        PhieuCham,
        on_delete=models.PROTECT,
        related_name="doi_chieu_gk2",
    )
    diem_gk1 = models.DecimalField(max_digits=5, decimal_places=2)
    diem_gk2 = models.DecimalField(max_digits=5, decimal_places=2)
    do_lech = models.DecimalField(max_digits=5, decimal_places=2)
    ket_qua = models.CharField(max_length=30, choices=KET_QUA_CHOICES)
    nguoi_doi_chieu = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="doi_chieu_cham_diem",
    )
    ghi_chu = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "doi_chieu_cham_diem"
        ordering = ["-created_at"]