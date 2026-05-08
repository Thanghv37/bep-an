from django import forms
from .models import MealReview

class MealReviewForm(forms.ModelForm):
    class Meta:
        model = MealReview
        fields = [
            'comment',
        ]
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Góp ý thêm về bữa ăn...'
            }),
        }