from django import forms
from django.contrib.auth.models import User

from .models import UserProfile


class UserCreateForm(forms.Form):
    # Nhân viên bếp thuê ngoài: không có mã NV, đăng nhập bằng SĐT + mật khẩu.
    login_by_password = forms.BooleanField(
        label='Nhân viên bếp thuê ngoài — đăng nhập bằng mật khẩu (tài khoản = SĐT)',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    employee_code = forms.CharField(label='Mã nhân viên', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    full_name = forms.CharField(label='Họ và tên', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    gender = forms.ChoiceField(label='Giới tính', required=False, choices=[('', '---------')] + UserProfile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    date_of_birth = forms.DateField(label='Ngày sinh', required=False, widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'))
    unit = forms.CharField(label='Đơn vị', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'unit_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    department = forms.CharField(label='Phòng ban', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'department_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    position = forms.CharField(label='Chức vụ', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'position_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    phone = forms.CharField(label='Số điện thoại', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(label='Vai trò', required=False, choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    def clean_employee_code(self):
        # Chỉ strip; kiểm tra bắt buộc/trùng để ở clean() vì phụ thuộc
        # login_by_password (thuê ngoài dùng SĐT làm username, không cần mã NV).
        return (self.cleaned_data.get('employee_code') or '').strip()

    def clean_phone(self):
        return (self.cleaned_data.get('phone') or '').strip()

    def clean(self):
        cleaned = super().clean()
        by_password = cleaned.get('login_by_password')
        code = cleaned.get('employee_code') or ''
        phone = cleaned.get('phone') or ''

        if by_password:
            # Tài khoản = SĐT. Không cần mã NV; vai trò cố định Nhân viên bếp.
            if not phone:
                self.add_error('phone', 'Nhân viên thuê ngoài cần Số điện thoại (dùng làm tài khoản đăng nhập).')
            elif User.objects.filter(username=phone).exists():
                self.add_error('phone', 'Số điện thoại này đã được dùng làm tài khoản.')
        else:
            if not code:
                self.add_error('employee_code', 'Vui lòng nhập Mã nhân viên.')
            elif User.objects.filter(username=code).exists():
                self.add_error('employee_code', 'Mã nhân viên này đã tồn tại.')
            if not cleaned.get('role'):
                self.add_error('role', 'Vui lòng chọn vai trò.')
        return cleaned


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'employee_code',
            'full_name',
            'email',
            'gender',
            'date_of_birth',
            'unit',
            'department',
            'position',
            'phone',
            'role',
        ]

        widgets = {
            'employee_code': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'list': 'unit_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'list': 'department_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'list': 'position_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
    
class ImportUserForm(forms.Form):
    file = forms.FileField(
        label='File Excel',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

