from django import forms
from .models import MealReview


SCORE_CHOICES = [
    ('', 'Chưa chọn'),   # 🔥 quan trọng: không có default
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4'),
    (5, '5'),
]


class MealReviewForm(forms.ModelForm):
    class Meta:
        model = MealReview
        fields = [
            'food_quality_score',
            'taste_score',
            'freshness_score',
            'portion_score',
            'hygiene_score',
            'overall_score',
            'comment',
        ]

        widgets = {
            'food_quality_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'taste_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'freshness_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'portion_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'hygiene_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'overall_score': forms.Select(
                choices=SCORE_CHOICES,
                attrs={'class': 'd-none star-score-input'}
            ),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Góp ý thêm về bữa ăn...'
            }),
        }

    # 🔥 VALIDATE BACKEND (bắt buộc chọn đủ)
    def clean(self):
        cleaned_data = super().clean()

        required_fields = [
            'food_quality_score',
            'taste_score',
            'freshness_score',
            'portion_score',
            'hygiene_score',
            'overall_score',
        ]

        for field in required_fields:
            value = cleaned_data.get(field)

            if value in [None, '', 0]:
                raise forms.ValidationError(
                    'Vui lòng đánh giá đầy đủ tất cả tiêu chí.'
                )

        return cleaned_data