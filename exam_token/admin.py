from django.contrib import admin

from .models import (
    BaiThiScanDiem,
    CanBo,
    ChamDiemChiTiet,
    ExamSessionLog,
    GanTokenBaiThi,
    HocVien,
    Lop,
    MonHoc,
    PhienThi,
    QRBatch,
    QRTokenBaiThi,
)


@admin.register(CanBo)
class CanBoAdmin(admin.ModelAdmin):
    list_display = ('ma_can_bo', 'ten_can_bo', 'cap_bac', 'chuc_vu', 'don_vi', 'trang_thai')
    search_fields = ('ma_can_bo', 'ten_can_bo', 'user__username')


@admin.register(PhienThi)
class PhienThiAdmin(admin.ModelAdmin):
    list_display = ('ma_phien_thi', 'mon', 'lop', 'ngay_thi', 'phong_thi', 'trang_thai', 'thoi_gian_lam_bai')
    list_filter = ('trang_thai', 'ngay_thi', 'mon', 'lop')
    search_fields = ('ma_phien_thi', 'phong_thi')


@admin.register(QRTokenBaiThi)
class QRTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'batch', 'trang_thai', 'created_at')
    list_filter = ('trang_thai', 'batch')
    search_fields = ('token',)


admin.site.register(Lop)
admin.site.register(MonHoc)
admin.site.register(HocVien)
admin.site.register(QRBatch)
admin.site.register(GanTokenBaiThi)
admin.site.register(BaiThiScanDiem)
admin.site.register(ChamDiemChiTiet)
admin.site.register(ExamSessionLog)
