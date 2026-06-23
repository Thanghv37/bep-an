from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    RATING_MIN = 1
    RATING_MAX = 5

    meal_review = models.ForeignKey(MealReview, on_delete=models.CASCADE, related_name='dish_reviews')
    dish = models.ForeignKey('meals.Dish', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(RATING_MIN), MaxValueValidator(RATING_MAX)],
        verbose_name='Số sao (1-5)'
    )

    class Meta:
        unique_together = ('meal_review', 'dish')
        verbose_name = 'Đánh giá món ăn'
        verbose_name_plural = 'Đánh giá món ăn'

    def __str__(self):
        return f'{self.dish.name} - {self.rating}★'


class DishSuggestion(models.Model):
    """Người dùng đề xuất tên món mới muốn bếp nấu. Dedupe theo `name_normalized`.
    Mỗi user chỉ vote 1 lần / món (tracked qua `DishSuggestionVote`). `count` là
    số voter unique, denormalize để query nhanh.
    """
    name = models.CharField(max_length=120, verbose_name='Tên món đề xuất')
    name_normalized = models.CharField(max_length=120, unique=True)
    count = models.PositiveIntegerField(default=1, verbose_name='Số voter')
    created_at = models.DateTimeField(auto_now_add=True)
    last_voted_at = models.DateTimeField(auto_now=True)
    last_voted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        ordering = ['-count', '-last_voted_at']
        verbose_name = 'Đề xuất món ăn'
        verbose_name_plural = 'Đề xuất món ăn'

    def __str__(self):
        return f'{self.name} ({self.count})'

    @staticmethod
    def normalize(name):
        import re
        return re.sub(r'\s+', ' ', (name or '').strip().lower())


class DishSuggestionVote(models.Model):
    """Track ai đã vote món nào để 1 user chỉ vote 1 lần / món."""
    suggestion = models.ForeignKey(DishSuggestion, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('suggestion', 'user')
        verbose_name = 'Vote đề xuất món'
        verbose_name_plural = 'Vote đề xuất món'


class ReviewInviteFeedback(models.Model):
    """Ý kiến của mọi người về tin nhắn MỜI ĐÁNH GIÁ gửi lúc 13h: có thấy
    phiền không. Thu thập để quyết định có nên tiếp tục gửi tin mời hay không.

    Vote 1 lần / người (latest thắng): nếu đăng nhập thì khóa theo `user`,
    nếu ẩn danh (trang công khai) thì khóa theo `session_key`. `annoyed=True`
    = thấy phiền, `False` = không phiền.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name='Người vote',
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, verbose_name='Session ẩn danh')
    annoyed = models.BooleanField(verbose_name='Thấy phiền?')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Ý kiến tin mời đánh giá'
        verbose_name_plural = 'Ý kiến tin mời đánh giá'
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='unique_invite_feedback_user',
            ),
            models.UniqueConstraint(
                fields=['session_key'],
                condition=models.Q(user__isnull=True, session_key__isnull=False),
                name='unique_invite_feedback_session',
            ),
        ]

    def __str__(self):
        who = self.user.username if self.user else f'Ẩn danh ({self.session_key})'
        return f'{who} - {"phiền" if self.annoyed else "không phiền"}'