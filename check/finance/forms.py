from django import forms
from .models import DailyPurchase


class DailyPurchaseForm(forms.ModelForm):
    class Meta:
        model = DailyPurchase
        fields = [
            'date',
            'purchase_type',
            'actual_cost',
            'bill_image',
            'note',
        ]

        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),

            'purchase_type': forms.RadioSelect(attrs={
                'class': 'form-check-input'
            }),

            'actual_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: 2500000'
            }),

            'bill_image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),

            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ghi chú thêm về đơn hàng / nhà cung cấp / phát sinh...'
            }),
        }

    def clean_bill_image(self):
        image = self.cleaned_data.get('bill_image')

        if not image and not self.instance.pk:
            raise forms.ValidationError("Bạn phải upload ảnh bill.")

        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Ảnh bill không được vượt quá 5MB.")

        return image