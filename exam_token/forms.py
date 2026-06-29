from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password

from .constants import EXAM_MINUTE_CHOICES, ROLE_CHOICES
from .models import CanBo, Lop, MonHoc, PhienThi

class PhienThiForm(forms.ModelForm):
    # Khai báo các trường bổ sung hoặc cần ghi đè
    ten_ky_thi = forms.CharField(label='Tên kỳ thi', max_length=150)   
    thoi_gian_lam_bai = forms.TypedChoiceField(
        label='Thời gian làm bài', 
        choices=EXAM_MINUTE_CHOICES, 
        coerce=int
    )
    
    # Ép kiểu thành CharField để trở thành ô text nhập tay thay vì Select Box
    can_bo_coi_thi_1 = forms.CharField(
    label="Cán bộ coi thi 1",
    max_length=150,
    required=False,
    widget=forms.TextInput(attrs={
        "placeholder": "Nhập họ tên cán bộ coi thi 1"
        }),
    )

    can_bo_coi_thi_2 = forms.CharField(
        label="Cán bộ coi thi 2",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Nhập họ tên cán bộ coi thi 2"
        }),
    )

    class Meta:
        model = PhienThi
        # Đã thay thế 2 chuỗi rỗng '' thành 'ten_ky_thi'
        fields = [
            'mon', 'lop', 'ten_ky_thi', 'ngay_thi', 
            'phong_thi', 'thoi_gian_lam_bai',
            'can_bo_coi_thi_1', 'can_bo_coi_thi_2', 
            'ghi_chu'
        ]
        
        # Thiết lập label tiếng Việt cho các trường thuộc Model
        labels = {
            'mon': 'Môn thi',
            'lop': 'Lớp học',
            'ngay_thi': 'Ngày thi',
            'phong_thi': 'Phòng thi',
            'ghi_chu': 'Ghi chú',
        }
        
        widgets = {
            'ngay_thi': forms.DateInput(attrs={'type': 'date'}),
            'ghi_chu': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Chỉ giới hạn queryset cho Môn và Lớp
        self.fields['mon'].queryset = MonHoc.objects.order_by('ma_mon')
        self.fields['lop'].queryset = Lop.objects.order_by('ma_lop')
        
        # Áp dụng Tailwind CSS cho tất cả các field
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                'class', 
                'mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100'
            )


class StaffUserForm(forms.Form):
    username = forms.CharField(label='Tài khoản', max_length=150)
    password = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput, required=False, help_text='Bỏ trống để tự sinh 12345678')
    role = forms.ChoiceField(label='Nhóm quyền', choices=ROLE_CHOICES)
    ma_can_bo = forms.CharField(label='Mã cán bộ', max_length=50)
    ten_can_bo = forms.CharField(label='Tên cán bộ', max_length=255)
    ngay_sinh = forms.DateField(label='Ngày sinh', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    gioi_tinh = forms.CharField(label='Giới tính', max_length=20, required=False)
    cap_bac = forms.CharField(label='Cấp bậc', max_length=100, required=False)
    chuc_vu = forms.CharField(label='Chức vụ', max_length=150, required=False)
    don_vi = forms.CharField(label='Đơn vị', max_length=255, required=False)
    sdt = forms.CharField(label='SĐT', max_length=30, required=False)
    email = forms.EmailField(label='Email', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100')

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Tài khoản đã tồn tại.')
        return username

    def clean_ma_can_bo(self):
        ma = self.cleaned_data['ma_can_bo']
        if CanBo.objects.filter(ma_can_bo=ma).exists():
            raise forms.ValidationError('Mã cán bộ đã tồn tại.')
        return ma

    def clean_password(self):
        password = self.cleaned_data.get('password') or '12345678'
        validate_password(password)
        return password

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(username=data['username'], password=data['password'], email=data.get('email') or '')
        user.first_name = data['ten_can_bo']
        if data['role'] == 'admin':
            user.is_staff = True
        user.save()
        group, _ = Group.objects.get_or_create(name=data['role'])
        user.groups.add(group)
        can_bo = CanBo.objects.create(
            user=user,
            ma_can_bo=data['ma_can_bo'],
            ten_can_bo=data['ten_can_bo'],
            ngay_sinh=data.get('ngay_sinh'),
            gioi_tinh=data.get('gioi_tinh'),
            cap_bac=data.get('cap_bac'),
            chuc_vu=data.get('chuc_vu'),
            don_vi=data.get('don_vi'),
            sdt=data.get('sdt'),
            email=data.get('email'),
        )
        return user, can_bo
