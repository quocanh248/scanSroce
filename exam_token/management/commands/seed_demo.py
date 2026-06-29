from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from exam_token.models import CanBo, Lop, MonHoc, HocVien


class Command(BaseCommand):
    help = 'Tạo dữ liệu mẫu tối thiểu để test.'

    def handle(self, *args, **options):
        for g in ['admin', 'quan_ly_thi', 'can_bo_coi_thi', 'can_bo_cham_diem', 'viewer']:
            Group.objects.get_or_create(name=g)
        admin, created = User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True})
        if created:
            admin.set_password('12345678')
            admin.save()
        cb_user, created = User.objects.get_or_create(username='coithi', defaults={'first_name': 'Lê Văn An'})
        if created:
            cb_user.set_password('12345678')
            cb_user.save()
        cb_user.groups.add(Group.objects.get(name='can_bo_coi_thi'))
        CanBo.objects.get_or_create(user=cb_user, defaults={'ma_can_bo': 'CB001', 'ten_can_bo': 'Lê Văn An', 'cap_bac': 'Thượng úy', 'chuc_vu': 'Cán bộ'})
        m, _ = MonHoc.objects.get_or_create(ma_mon='TOAN', defaults={'ten_mon': 'Toán học'})
        lop, _ = Lop.objects.get_or_create(ma_lop='12A1', defaults={'ten_lop': '12A1'})
        for i in range(1, 21):
            HocVien.objects.get_or_create(ma_hoc_vien=f'HV{i:03d}', defaults={'so_bao_danh': i, 'ho_ten': f'Học viên {i:02d}', 'lop': lop})
        self.stdout.write(self.style.SUCCESS('Đã tạo dữ liệu mẫu. Admin: admin/12345678, Coi thi: coithi/12345678'))
