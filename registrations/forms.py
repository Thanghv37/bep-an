from django import forms

from accounts.models import UserProfile

from .models import MealRegistration
from .options import get_meal_options, get_kitchen_options


STATUS_FIXED = 'Đặt thành công'


class MealRegistrationForm(forms.ModelForm):
    class Meta:
        model = MealRegistration
        fields = [
            'employee_code',
            'full_name',
            'date',
            'meal_name',
            'kitchen_name',
            'quantity',
            'status',
        ]

        widgets = {
            'employee_code': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_employee_code',
                'autocomplete': 'off',
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control bg-light',
                'id': 'id_full_name',
                'readonly': 'readonly',
                'placeholder': 'Tự động điền sau khi nhập mã NV hợp lệ',
            }),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'meal_name': forms.Select(attrs={'class': 'form-select'}),
            'kitchen_name': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.TextInput(attrs={
                'class': 'form-control bg-light',
                'readonly': 'readonly',
                'tabindex': '-1',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dropdown choices nạp động từ SystemConfig (admin sửa qua trang options).
        meal_choices = [(opt, opt) for opt in get_meal_options()]
        kitchen_choices = [(opt, opt) for opt in get_kitchen_options()]
        self.fields['meal_name'] = forms.ChoiceField(
            choices=[('', '— Chọn bữa ăn —')] + meal_choices,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label=MealRegistration._meta.get_field('meal_name').verbose_name,
        )
        self.fields['kitchen_name'] = forms.ChoiceField(
            choices=[('', '— Chọn bếp ăn —')] + kitchen_choices,
            widget=forms.Select(attrs={'class': 'form-select'}),
            label=MealRegistration._meta.get_field('kitchen_name').verbose_name,
        )

        # Trạng thái: cố định "Đặt thành công", user không sửa.
        self.fields['status'].initial = STATUS_FIXED
        self.fields['status'].required = False

    def clean_employee_code(self):
        code = (self.cleaned_data.get('employee_code') or '').strip()
        if not code:
            raise forms.ValidationError('Vui lòng nhập mã nhân viên.')
        if not UserProfile.objects.filter(employee_code=code).exists():
            raise forms.ValidationError(
                'Mã nhân viên không tồn tại trong hệ thống. '
                'Vui lòng tạo tài khoản ở trang Quản lý người dùng trước.'
            )
        return code

    def clean_status(self):
        # Backend force giá trị, không tin client (input đang readonly nhưng
        # có thể bị tamper qua DevTools).
        return STATUS_FIXED
