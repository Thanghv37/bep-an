from django.db import models
from django.db.models import Sum

class MealRegistration(models.Model):
    employee_code = models.CharField(max_length=50, verbose_name='Mã nhân viên')
    full_name = models.CharField(max_length=255, blank=True, verbose_name='Họ và tên')

    date = models.DateField(verbose_name='Ngày đặt cơm')

    meal_name = models.CharField(max_length=100, blank=True, verbose_name='Bữa ăn')
    kitchen_name = models.CharField(max_length=255, blank=True, verbose_name='Tên bếp ăn')

    quantity = models.PositiveIntegerField(default=1, verbose_name='Số suất đặt')
    status = models.CharField(max_length=100, blank=True, verbose_name='Trạng thái')

    source = models.CharField(max_length=50, default='excel', verbose_name='Nguồn dữ liệu')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'employee_code']
        unique_together = ('employee_code', 'date', 'meal_name', 'kitchen_name')
        verbose_name = 'Đăng kí suất ăn'
        verbose_name_plural = 'Đăng kí suất ăn'

    def __str__(self):
        return f'{self.employee_code} - {self.date} - {self.quantity}'
def get_registered_count(target_date):
    total = MealRegistration.objects.filter(
        date=target_date
    ).aggregate(total=Sum('quantity'))['total']

    return total or 0

class NotificationLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Thành công'),
        ('failed', 'Thất bại'),
    ]
    target_date = models.DateField(verbose_name='Ngày đăng ký')
    employee_code = models.CharField(max_length=50, verbose_name='Mã nhân viên')
    full_name = models.CharField(max_length=255, blank=True, verbose_name='Họ và tên')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='Trạng thái')
    error_message = models.TextField(blank=True, null=True, verbose_name='Chi tiết lỗi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian gửi')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log gửi tin nhắn'
        verbose_name_plural = 'Log gửi tin nhắn'

    def __str__(self):
        return f'{self.employee_code} - {self.target_date} - {self.status}'