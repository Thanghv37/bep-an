from django.conf import settings
from django.db import models

class MealReview(models.Model):
    date = models.DateField(verbose_name='Ngày đánh giá')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Người đánh giá',
        null=True, blank=True
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, verbose_name='Session Key ẩn danh')

    comment = models.TextField(blank=True, verbose_name='Góp ý thêm')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-updated_at']
        verbose_name = 'Đánh giá bữa ăn'
        verbose_name_plural = 'Đánh giá bữa ăn'
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'user'], 
                condition=models.Q(user__isnull=False),
                name='unique_user_date_review'
            )
        ]

    def __str__(self):
        user_display = self.user.username if self.user else f'Ẩn danh ({self.session_key})'
        return f'{self.date} - {user_display}'

class DishReview(models.Model):
    LIKE = 'like'
    DISLIKE = 'dislike'
    CHOICES = [
        (LIKE, 'Thích'),
        (DISLIKE, 'Không thích'),
    ]
    
    meal_review = models.ForeignKey(MealReview, on_delete=models.CASCADE, related_name='dish_reviews')
    dish = models.ForeignKey('meals.Dish', on_delete=models.CASCADE, related_name='reviews')
    evaluation = models.CharField(max_length=10, choices=CHOICES, verbose_name='Đánh giá')

    class Meta:
        unique_together = ('meal_review', 'dish')
        verbose_name = 'Đánh giá món ăn'
        verbose_name_plural = 'Đánh giá món ăn'

    def __str__(self):
        return f'{self.dish.name} - {self.get_evaluation_display()}'