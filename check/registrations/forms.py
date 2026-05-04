from django import forms
from .models import MealRegistration


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
            'employee_code': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'meal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'kitchen_name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.TextInput(attrs={'class': 'form-control'}),
        }