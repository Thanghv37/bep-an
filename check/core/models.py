from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MealPriceSetting(models.Model):
    start_date = models.DateField(verbose_name='Từ ngày')
    end_date = models.DateField(null=True, blank=True, verbose_name='Đến ngày')
    meal_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        verbose_name='Giá suất ăn'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Cấu hình giá suất ăn'
        verbose_name_plural = 'Cấu hình giá suất ăn'

    def __str__(self):
        return f"{self.start_date} - {self.end_date or '∞'} : {self.meal_price}"

    def clean(self):
        from django.utils import timezone

        today = timezone.localdate()

        if self.start_date < today:
            raise ValidationError({
                'start_date': 'Không được thiết lập giá bắt đầu từ ngày trong quá khứ.'
            })

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'Đến ngày phải lớn hơn hoặc bằng Từ ngày.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()

        overlapping_qs = MealPriceSetting.objects.exclude(pk=self.pk)

        for item in overlapping_qs:
            current_start = self.start_date
            current_end = self.end_date

            other_start = item.start_date
            other_end = item.end_date

            if current_end is None and other_end is None:
                overlap = True
            elif current_end is None:
                overlap = current_start <= other_end
            elif other_end is None:
                overlap = other_start <= current_end
            else:
                overlap = current_start <= other_end and other_start <= current_end

            if overlap:
                if other_start < current_start:
                    new_end = current_start - timedelta(days=1)

                    if new_end < other_start:
                        item.delete()
                    else:
                        item.end_date = new_end
                        item.save(update_fields=['end_date', 'updated_at'])
                else:
                    item.delete()

        super().save(*args, **kwargs)


class MealPriceChangeLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Tạo mới'),
        ('update', 'Cập nhật'),
    ]

    meal_price_setting = models.ForeignKey(
        MealPriceSetting,
        on_delete=models.CASCADE,
        related_name='change_logs',
        verbose_name='Cấu hình giá'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='Hành động')
    old_start_date = models.DateField(null=True, blank=True, verbose_name='Từ ngày cũ')
    old_end_date = models.DateField(null=True, blank=True, verbose_name='Đến ngày cũ')
    old_meal_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Giá cũ')
    new_start_date = models.DateField(verbose_name='Từ ngày mới')
    new_end_date = models.DateField(null=True, blank=True, verbose_name='Đến ngày mới')
    new_meal_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Giá mới')
    reason = models.TextField(blank=True, verbose_name='Lý do thay đổi')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Người thay đổi'
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Log thay đổi giá suất ăn'
        verbose_name_plural = 'Log thay đổi giá suất ăn'

    def __str__(self):
        return f"{self.get_action_display()} - {self.changed_at:%d/%m/%Y %H:%M}"