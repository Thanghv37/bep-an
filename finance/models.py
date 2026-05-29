from django.db import models
from django.contrib.auth import get_user_model
from datetime import datetime
from django.utils import timezone
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
        (PURCHASE_TYPE_MAIN, 'Mua thực phẩm'),
        (PURCHASE_TYPE_EXTRA, 'Mua gia vị'),
    ]

    # BỎ unique=True để 1 ngày có thể nhập nhiều bill
    date = models.DateField(verbose_name='Ngày')

    purchase_type = models.CharField(
        max_length=20,
        choices=PURCHASE_TYPE_CHOICES,
        default=PURCHASE_TYPE_MAIN,
        verbose_name='Phân loại'
    )
    extra_request = models.ForeignKey(
        'ExtraPurchaseRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchases',
        verbose_name='Đơn mua bổ sung liên kết'
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

    was_edited_after_approval = models.BooleanField(
        default=False,
        verbose_name='Đã chỉnh sửa sau khi duyệt'
    )

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Chi phí mua hàng ngày'
        verbose_name_plural = 'Chi phí mua hàng ngày'

    def __str__(self):
        return f"{self.date} - {self.get_purchase_type_display()} - {self.actual_cost}"


class PurchaseEditLog(models.Model):
    purchase = models.ForeignKey(
        DailyPurchase,
        on_delete=models.CASCADE,
        related_name='edit_logs',
        verbose_name='Chi phí'
    )
    edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Người chỉnh sửa'
    )
    edited_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm sửa')
    previous_status = models.CharField(max_length=20, blank=True, verbose_name='Trạng thái trước khi sửa')
    reason = models.TextField(verbose_name='Lý do chỉnh sửa')

    class Meta:
        ordering = ['-edited_at']
        verbose_name = 'Lịch sử chỉnh sửa chi phí'
        verbose_name_plural = 'Lịch sử chỉnh sửa chi phí'

    def __str__(self):
        return f"Edit #{self.purchase_id} by {self.edited_by} at {self.edited_at}"


class PurchaseExtraItem(models.Model):
    purchase = models.ForeignKey(
        DailyPurchase,
        on_delete=models.CASCADE,
        related_name='extra_items',
        verbose_name='Phiếu mua bổ sung'
    )

    date = models.DateField(null=True, blank=True, verbose_name='Ngày')

    ingredient_name = models.CharField(max_length=255, verbose_name='Nguyên liệu')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Số lượng')
    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0,
        verbose_name='Đơn giá'
    )

    class Meta:
        verbose_name = 'Mặt hàng trong hóa đơn'
        verbose_name_plural = 'Mặt hàng trong hóa đơn'

    def __str__(self):
        return f"{self.date} - {self.ingredient_name}"

    @property
    def line_total(self):
        """Thành tiền = số lượng × đơn giá (làm tròn)."""
        return int((self.quantity or 0) * (self.unit_price or 0))


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
class InventoryEntry(models.Model):
    """Tồn kho (tủ lạnh) thực phẩm còn lại sau mỗi ngày nấu.

    Mô hình theo TỪNG NGÀY (lịch sử): mỗi (ngày, nguyên liệu, đơn vị) là 1 dòng.
    Lưu thêm cùng (ngày, nguyên liệu, đơn vị) -> CỘNG DỒN quantity (mua nhiều
    lần / nhiều hóa đơn cùng loại trong ngày).

    Nguồn nhập:
    - 'manual': nhân viên tự nhập tay.
    - 'invoice': trích từ hóa đơn (PurchaseExtraItem) ngày đó, chọn khối lượng tồn.
    """
    SOURCE_MANUAL = 'manual'
    SOURCE_INVOICE = 'invoice'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Nhập tay'),
        (SOURCE_INVOICE, 'Từ hóa đơn'),
    ]

    stored_date = models.DateField(verbose_name='Ngày lưu tồn')
    ingredient_name = models.CharField(max_length=255, verbose_name='Nguyên liệu')
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Khối lượng tồn'
    )
    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')

    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL,
        verbose_name='Nguồn nhập'
    )
    note = models.TextField(blank=True, verbose_name='Ghi chú')

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Người nhập'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ingredient_name']
        verbose_name = 'Tồn kho'
        verbose_name_plural = 'Tồn kho'

    def __str__(self):
        return f'{self.ingredient_name} - {self.quantity}{self.unit}'


class InventoryLog(models.Model):
    """Lịch sử nhập / xuất kho — mỗi thao tác 1 dòng, không bị ảnh hưởng khi
    InventoryEntry bị xóa (tồn về 0)."""
    ACTION_IMPORT = 'import'
    ACTION_EXPORT = 'export'
    ACTION_CHOICES = [
        (ACTION_IMPORT, 'Nhập kho'),
        (ACTION_EXPORT, 'Xuất kho'),
    ]

    action = models.CharField(max_length=10, choices=ACTION_CHOICES, verbose_name='Thao tác')
    action_date = models.DateField(verbose_name='Ngày')
    ingredient_name = models.CharField(max_length=255, verbose_name='Nguyên liệu')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Khối lượng')
    unit = models.CharField(max_length=50, blank=True, verbose_name='Đơn vị')
    source = models.CharField(max_length=20, blank=True, verbose_name='Nguồn')
    note = models.TextField(blank=True, verbose_name='Ghi chú')

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Người thực hiện'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lịch sử kho'
        verbose_name_plural = 'Lịch sử kho'

    def __str__(self):
        return f'{self.get_action_display()} {self.ingredient_name} {self.quantity}{self.unit}'


class ExtraPurchaseRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ phê duyệt'),
        (STATUS_APPROVED, 'Đã duyệt'),
        (STATUS_REJECTED, 'Từ chối'),
    ]

    date = models.DateField()
    note = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_extra_requests')
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
class ExtraPurchaseRequestItem(models.Model):
    request = models.ForeignKey(
        ExtraPurchaseRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )

    ingredient_name = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=14, decimal_places=0, default=0)
