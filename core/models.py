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
    spice_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='Giá gia vị mỗi suất'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Cấu hình giá suất ăn'
        verbose_name_plural = 'Cấu hình giá suất ăn'

    def __str__(self):
        return f"{self.start_date} - {self.end_date or '∞'} : {self.meal_price}"

    @property
    def food_price(self):
        """Giá thực phẩm mỗi suất = giá suất ăn - giá gia vị."""
        return int(self.meal_price or 0) - int(self.spice_price or 0)

    def clean(self):
        # Cho phép cấu hình giá cho ngày trong quá khứ (vd: nhập lại giá đã thực
        # thi nhưng quên log). Lịch năm sẽ đánh dấu vàng các ngày quá khứ bị sửa
        # để dễ rà soát.
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'Đến ngày phải lớn hơn hoặc bằng Từ ngày.'
            })

        if self.spice_price is not None and self.spice_price < 0:
            raise ValidationError({
                'spice_price': 'Giá gia vị không được là số âm.'
            })

        if (self.meal_price is not None and self.spice_price is not None
                and self.spice_price > self.meal_price):
            raise ValidationError({
                'spice_price': 'Giá gia vị không được lớn hơn giá suất ăn.'
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
    old_spice_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name='Giá gia vị cũ')
    new_start_date = models.DateField(verbose_name='Từ ngày mới')
    new_end_date = models.DateField(null=True, blank=True, verbose_name='Đến ngày mới')
    new_meal_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Giá mới')
    new_spice_price = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Giá gia vị mới')
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
class DailyNutritionAnalysis(models.Model):
    date = models.DateField(unique=True)
    total_kcal = models.PositiveIntegerField(default=0)
    level = models.CharField(max_length=50, blank=True)
    summary = models.TextField(blank=True)
    raw_json = models.JSONField(default=dict, blank=True)

    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.total_kcal} kcal"
# core/models.py
class AttendanceLog(models.Model):
    employee_code = models.CharField(max_length=50)
    full_name = models.CharField(max_length=255, blank=True)
    scan_time = models.DateTimeField()
    type = models.CharField(max_length=50, default="bếp ăn")
    status = models.CharField(max_length=20, choices=[("Đã đăng ký", "Đã đăng ký"), ("Chưa đăng ký", "Chưa đăng ký")])

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee_code} | {self.scan_time} | {self.status}"
class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    def __str__(self):
        return self.key


class RecognitionHeartbeat(models.Model):
    """Trạng thái sống của 1 camera nhận diện. Client gửi heartbeat định kỳ,
    server chỉ giữ 1 row mỗi camera (camera_id là khóa chính)."""
    camera_id = models.CharField(max_length=64, primary_key=True, verbose_name='Mã camera')
    last_heartbeat_at = models.DateTimeField(verbose_name='Heartbeat gần nhất')
    last_info = models.JSONField(null=True, blank=True, verbose_name='Thông tin kèm theo')

    class Meta:
        verbose_name = 'Heartbeat camera nhận diện'
        verbose_name_plural = 'Heartbeat camera nhận diện'

    def __str__(self):
        return f"{self.camera_id} @ {self.last_heartbeat_at:%d/%m/%Y %H:%M:%S}"


class AttendanceCapture(models.Model):
    """Ảnh chụp khung hình lúc camera nhận diện được 1 nhân viên. Chỉ lưu cho
    người nhận diện ra mã NV (không lưu 'Unknown'). Tự xóa sau 30 ngày."""
    employee_code = models.CharField(max_length=50, db_index=True, verbose_name='Mã nhân viên')
    camera_id = models.CharField(max_length=64, blank=True, verbose_name='Mã camera')
    scan_time = models.DateTimeField(db_index=True, verbose_name='Thời gian quét')
    status = models.CharField(max_length=30, blank=True, verbose_name='Trạng thái')
    score = models.FloatField(null=True, blank=True, verbose_name='Độ khớp')
    image = models.ImageField(upload_to='attendance_captures/%Y/%m/%d/', verbose_name='Ảnh chụp')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scan_time']
        verbose_name = 'Ảnh chụp nhận diện'
        verbose_name_plural = 'Ảnh chụp nhận diện'

    def __str__(self):
        return f"{self.employee_code} @ {self.scan_time:%d/%m/%Y %H:%M:%S}"


class CameraStatusLog(models.Model):
    """Lịch sử chuyển trạng thái online/offline của camera nhận diện —
    mỗi lần đổi trạng thái ghi 1 dòng. `changed_at` là thời điểm thực tế
    của sự kiện (vd offline = last_heartbeat + ngưỡng), không phải lúc ghi."""
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
    ]
    camera_id = models.CharField(max_length=64, db_index=True, verbose_name='Mã camera')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name='Trạng thái')
    changed_at = models.DateTimeField(db_index=True, verbose_name='Thời điểm chuyển')

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'Log trạng thái camera'
        verbose_name_plural = 'Log trạng thái camera'

    def __str__(self):
        return f"{self.camera_id} → {self.status} @ {self.changed_at:%d/%m/%Y %H:%M:%S}"


class BirthdayGreetingLog(models.Model):
    """Đánh dấu một nhân viên đã được chiếu màn chúc mừng sinh nhật trong ngày,
    để màn TV không chiếu lặp lại mỗi nhịp poll. Mỗi (mã NV, ngày) chỉ 1 dòng."""
    employee_code = models.CharField(max_length=50, verbose_name='Mã nhân viên')
    greeting_date = models.DateField(db_index=True, verbose_name='Ngày chúc mừng')
    shown_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm chiếu')

    class Meta:
        unique_together = ('employee_code', 'greeting_date')
        verbose_name = 'Log chúc mừng sinh nhật'
        verbose_name_plural = 'Log chúc mừng sinh nhật'

    def __str__(self):
        return f"{self.employee_code} @ {self.greeting_date:%d/%m/%Y}"