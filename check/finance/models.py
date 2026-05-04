from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime

User = get_user_model()


def upload_bill_image(instance, filename):
    ext = filename.split('.')[-1].lower()

    if instance.date:
        date_str = instance.date.strftime('%Y_%m_%d')
    else:
        date_str = datetime.now().strftime('%Y_%m_%d')

    purchase_type = getattr(instance, 'purchase_type', 'bill')
    return f'purchase_bills/{date_str}_{purchase_type}_bill.{ext}'


def upload_reject_bill_image(instance, filename):
    ext = filename.split('.')[-1].lower()

    if instance.date:
        date_str = instance.date.strftime('%Y_%m_%d')
    else:
        date_str = datetime.now().strftime('%Y_%m_%d')

    return f'purchase_reject_bills/{date_str}_reject_bill.{ext}'


class DailyPurchase(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ phê duyệt'),
        (STATUS_APPROVED, 'Đã duyệt'),
        (STATUS_REJECTED, 'Từ chối'),
    ]

    PURCHASE_TYPE_MAIN = 'main'
    PURCHASE_TYPE_EXTRA = 'extra'

    PURCHASE_TYPE_CHOICES = [
        (PURCHASE_TYPE_MAIN, 'Mua nguyên liệu chính'),
        (PURCHASE_TYPE_EXTRA, 'Mua bổ sung'),
    ]

    # BỎ unique=True để 1 ngày có thể nhập nhiều bill
    date = models.DateField(verbose_name='Ngày')

    purchase_type = models.CharField(
        max_length=20,
        choices=PURCHASE_TYPE_CHOICES,
        default=PURCHASE_TYPE_MAIN,
        verbose_name='Phân loại'
    )

    actual_cost = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0,
        verbose_name='Chi phí mua thực tế'
    )

    note = models.TextField(blank=True, verbose_name='Ghi chú')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Trạng thái'
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Người nhập'
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_purchases',
        verbose_name='Người phê duyệt'
    )

    bill_image = models.ImageField(
        upload_to=upload_bill_image,
        null=True,
        blank=True,
        verbose_name='Ảnh bill'
    )

    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời điểm phê duyệt')
    created_at = models.DateTimeField(auto_now_add=True)

    reject_reason = models.TextField(blank=True, verbose_name='Lý do từ chối')

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_purchases',
        verbose_name='Người từ chối'
    )

    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời điểm từ chối')

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Chi phí mua hàng ngày'
        verbose_name_plural = 'Chi phí mua hàng ngày'

    def __str__(self):
        return f"{self.date} - {self.get_purchase_type_display()} - {self.actual_cost}"


class PurchaseExtraItem(models.Model):
    purchase = models.ForeignKey(
        DailyPurchase,
        on_delete=models.CASCADE,
        related_name='extra_items',
        verbose_name='Phiếu mua bổ sung'
    )

    ingredient_name = models.CharField(max_length=255, verbose_name='Nguyên liệu')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Số lượng')
    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')

    class Meta:
        ordering = ['id']
        verbose_name = 'Nguyên liệu mua bổ sung'
        verbose_name_plural = 'Nguyên liệu mua bổ sung'

    def __str__(self):
        return f"{self.ingredient_name} - {self.quantity} {self.unit}"


class PurchaseRejectLog(models.Model):
    purchase = models.ForeignKey(
        DailyPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reject_logs',
        verbose_name='Chi phí'
    )

    date = models.DateField(verbose_name='Ngày chi phí')

    actual_cost = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0,
        verbose_name='Chi phí'
    )

    reject_reason = models.TextField(verbose_name='Lý do từ chối')

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_reject_logs',
        verbose_name='Người từ chối'
    )

    rejected_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm từ chối')

    created_by_username = models.CharField(max_length=150, blank=True, verbose_name='Mã người nhập')
    created_by_full_name = models.CharField(max_length=255, blank=True, verbose_name='Tên người nhập')
    note_snapshot = models.TextField(blank=True, verbose_name='Ghi chú tại thời điểm từ chối')

    bill_image_snapshot = models.ImageField(
        upload_to=upload_reject_bill_image,
        null=True,
        blank=True,
        verbose_name='Ảnh bill tại thời điểm từ chối'
    )

    class Meta:
        ordering = ['-rejected_at']
        verbose_name = 'Lịch sử từ chối chi phí'
        verbose_name_plural = 'Lịch sử từ chối chi phí'

    def __str__(self):
        return f"Từ chối chi phí {self.date} - {self.rejected_at:%d/%m/%Y %H:%M}"