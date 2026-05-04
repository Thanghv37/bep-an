from django.conf import settings
from django.db import models


class MealReview(models.Model):
    date = models.DateField(verbose_name='Ngày đánh giá')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Người đánh giá'
    )

    food_quality_score = models.PositiveSmallIntegerField(verbose_name='Chất lượng món ăn')
    taste_score = models.PositiveSmallIntegerField(verbose_name='Khẩu vị')
    freshness_score = models.PositiveSmallIntegerField(verbose_name='Độ nóng / độ tươi')
    portion_score = models.PositiveSmallIntegerField(verbose_name='Khẩu phần')
    hygiene_score = models.PositiveSmallIntegerField(verbose_name='Vệ sinh / trình bày')
    overall_score = models.PositiveSmallIntegerField(verbose_name='Hài lòng chung')

    comment = models.TextField(blank=True, verbose_name='Góp ý thêm')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('date', 'user')
        ordering = ['-date', '-updated_at']
        verbose_name = 'Đánh giá bữa ăn'
        verbose_name_plural = 'Đánh giá bữa ăn'

    def __str__(self):
        return f'{self.date} - {self.user.username}'

    @property
    def average_score(self):
        scores = [
            self.food_quality_score,
            self.taste_score,
            self.freshness_score,
            self.portion_score,
            self.hygiene_score,
            self.overall_score,
        ]
        return round(sum(scores) / len(scores), 2)