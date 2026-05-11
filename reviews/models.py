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


class FeedbackMessage(models.Model):
    """Tin nhắn góp ý user gửi cho bot qua DM trên NetChat.

    Được populate bằng management command `poll_feedback` chạy định kỳ.
    """

    mattermost_post_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='ID post trên NetChat',
    )
    channel_id = models.CharField(max_length=64)
    sender_username = models.CharField(max_length=100, verbose_name='Username NetChat')
    sender_full_name = models.CharField(max_length=255, blank=True, verbose_name='Họ tên')
    employee_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Mã nhân viên',
        help_text='Tự động lookup từ email trong UserProfile (để trống nếu không match)',
    )
    message = models.TextField(verbose_name='Nội dung tin nhắn')
    posted_at = models.DateTimeField(verbose_name='Thời điểm gửi (NetChat)')
    fetched_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm crawl về')

    class Meta:
        ordering = ['-posted_at']
        verbose_name = 'Góp ý qua NetChat'
        verbose_name_plural = 'Góp ý qua NetChat'
        indexes = [
            models.Index(fields=['-posted_at']),
        ]

    def __str__(self):
        return f'{self.sender_username} - {self.posted_at:%d/%m %H:%M}'