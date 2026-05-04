from django import forms
from accounts.permissions import is_admin
from .models import Dish, DailyMenu, Ingredient, DishIngredient


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ['name', 'dish_type', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ví dụ: Cá kho cà chua'
            }),
            'dish_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }


class DishIngredientForm(forms.Form):
    ingredient_name = forms.CharField(
        required=False,
        label='Nguyên liệu',
        widget=forms.TextInput(attrs={
            'class': 'form-control ingredient-name-input',
            'placeholder': 'Ví dụ: Cá, cà chua, hành...'
        })
    )

    quantity_per_person = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        label='Khẩu phần / người',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )

    unit = forms.ChoiceField(
        required=False,
        choices=Dish.UNIT_CHOICES,
        label='Đơn vị',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class DailyMenuForm(forms.ModelForm):
    dishes = forms.ModelMultipleChoiceField(
        queryset=Dish.objects.filter(
            is_active=True,
            status=getattr(Dish, 'STATUS_APPROVED', 'approved')
        ).order_by('dish_type', 'name'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Chọn món ăn'
    )

    edit_reason = forms.CharField(
        required=False,
        label='Lý do chỉnh sửa',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Nhập lý do chỉnh sửa'
        })
    )

    class Meta:
        model = DailyMenu
        fields = ['date', 'status', 'note', 'edit_reason', 'dishes']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ghi chú thêm cho thực đơn...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['dishes'].queryset = Dish.objects.filter(
            is_active=True,
            status=getattr(Dish, 'STATUS_APPROVED', 'approved')
        ).order_by('dish_type', 'name')

        if self.user and not is_admin(self.user):
            self.fields['status'].choices = [
                (DailyMenu.STATUS_PENDING, 'Chờ phê duyệt')
            ]

            self.initial['status'] = DailyMenu.STATUS_PENDING
            self.fields['status'].initial = DailyMenu.STATUS_PENDING

            if self.instance:
                self.instance.status = DailyMenu.STATUS_PENDING

            self.fields['status'].disabled = True