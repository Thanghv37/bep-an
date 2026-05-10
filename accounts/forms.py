from django import forms
from django.contrib.auth.models import User

from .models import UserProfile


class UserCreateForm(forms.Form):
    employee_code = forms.CharField(label='Mã nhân viên', widget=forms.TextInput(attrs={'class': 'form-control'}))
    full_name = forms.CharField(label='Họ và tên', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Email', required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    gender = forms.ChoiceField(label='Giới tính', required=False, choices=[('', '---------')] + UserProfile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    unit = forms.CharField(label='Đơn vị', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'unit_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    department = forms.CharField(label='Phòng ban', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'department_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    position = forms.CharField(label='Chức vụ', required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'position_choices', 'autocomplete': 'off', 'placeholder': 'Chọn hoặc nhập mới'}))
    phone = forms.CharField(label='Số điện thoại', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(label='Vai trò', choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    def clean_employee_code(self):
        employee_code = self.cleaned_data['employee_code'].strip()
        if User.objects.filter(username=employee_code).exists():
            raise forms.ValidationError('Mã nhân viên này đã tồn tại.')
        return employee_code


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'employee_code',
            'full_name',
            'email',
            'gender',
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

