from django import forms
from .models import MealPriceSetting


class MealPriceSettingForm(forms.ModelForm):
    reason = forms.CharField(
        required=True,
        label='Lý do thay đổi',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Nhập lý do tạo mới / cập nhật giá để công khai lịch sử thay đổi...'
        })
    )

    class Meta:
        model = MealPriceSetting
        fields = ['start_date', 'end_date', 'meal_price']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'meal_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 30000'
            }),
        }