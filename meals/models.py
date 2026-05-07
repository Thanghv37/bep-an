#meals/models

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
import os
import unicodedata
from django.utils.text import slugify
from django.utils import timezone
from registrations.models import get_registered_count
User = get_user_model()


def upload_dish_image(instance, filename):
    ext = filename.split('.')[-1].lower()

    name = unicodedata.normalize('NFKD', instance.name)
    name = name.encode('ascii', 'ignore').decode('ascii')
    slug = slugify(name).replace('-', '_')

    return f'dish_images/{slug}.{ext}'
def normalize_vietnamese_name(text):
    if not text:
        return text

    text = text.strip()

    return text[:1].upper() + text[1:].lower()




# =============================
# DISH (UPDATED WITH APPROVAL)
# =============================
class Dish(models.Model):
    DISH_TYPE_CHOICES = [
        ('main', 'Món chính'),
        ('side', 'Món phụ'),
        ('soup', 'Món canh'),
        ('dessert', 'Món tráng miệng'),
    ]

    UNIT_CHOICES = [
        ('g', 'Gram'),
        ('kg', 'Kg'),
        ('ml', 'Ml'),
        ('l', 'Lít'),
        ('phần', 'Phần'),
        ('quả', 'Quả'),
    ]
    def save(self, *args, **kwargs):
        self.name = normalize_vietnamese_name(self.name)

        super().save(*args, **kwargs)
    # 🔥 NEW: trạng thái
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ phê duyệt'),
        (STATUS_APPROVED, 'Đã duyệt'),
        (STATUS_REJECTED, 'Đã từ chối'),
    ]

    name = models.CharField(max_length=255, unique=True, verbose_name='Tên món')
    dish_type = models.CharField(max_length=20, choices=DISH_TYPE_CHOICES, verbose_name='Loại món')

    portion_per_person = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Khẩu phần / người')
    portion_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='g', verbose_name='Đơn vị')

    is_active = models.BooleanField(default=True, verbose_name='Đang sử dụng')

    # 🔥 NEW
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='Trạng thái'
    )

    reject_reason = models.TextField(blank=True, verbose_name='Lý do từ chối')

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_dishes',
        verbose_name='Người từ chối'
    )

    rejected_at = models.DateTimeField(null=True, blank=True)

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_dishes',
        verbose_name='Người duyệt'
    )

    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    image = models.ImageField(
        upload_to=upload_dish_image,
        null=True,
        blank=True,
        verbose_name='Ảnh món ăn'
    )
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# =============================
# DISH REJECT LOG (NEW)
# =============================
class DishRejectLog(models.Model):
    dish = models.ForeignKey(
        Dish,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reject_logs',
        verbose_name='Món ăn'
    )

    dish_name = models.CharField(max_length=255)
    dish_type = models.CharField(max_length=20, blank=True)

    reject_reason = models.TextField()

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dish_reject_logs'
    )

    rejected_at = models.DateTimeField(auto_now_add=True)

    created_by_username = models.CharField(max_length=150, blank=True)
    created_by_full_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-rejected_at']

    def __str__(self):
        return f"Từ chối món {self.dish_name}"


# =============================
# INGREDIENT
# =============================
class Ingredient(models.Model):
    UNIT_CHOICES = Dish.UNIT_CHOICES
    def save(self, *args, **kwargs):
        self.name = normalize_vietnamese_name(self.name)

        super().save(*args, **kwargs)
    name = models.CharField(max_length=255, unique=True)
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='g')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DishIngredient(models.Model):
    UNIT_CHOICES = Dish.UNIT_CHOICES

    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)

    quantity_per_person = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='g')

    class Meta:
        ordering = ['ingredient__name']
        unique_together = ('dish', 'ingredient', 'unit')

    def __str__(self):
        return f'{self.dish.name} - {self.ingredient.name}'


# =============================
# DAILY MENU
# =============================
class DailyMenu(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Chờ phê duyệt'),
        (STATUS_APPROVED, 'Đã duyệt'),
        (STATUS_REJECTED, 'Đã từ chối'),
    ]

    date = models.DateField(unique=True)
    note = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    edit_reason = models.TextField(blank=True)
    last_edited_at = models.DateTimeField(null=True, blank=True)

    reject_reason = models.TextField(blank=True)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_menus'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"Menu {self.date}"

    @property
    def registered_count(self):
        return get_registered_count(self.date)


class DailyMenuItem(models.Model):
    daily_menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']
        unique_together = ('daily_menu', 'dish')

    def __str__(self):
        return f"{self.daily_menu.date} - {self.dish.name}"

    def required_total_quantity(self):
        registered_count = get_registered_count(self.daily_menu.date)
        return registered_count * self.dish.portion_per_person


# =============================
# MENU REJECT LOG
# =============================
class MenuRejectLog(models.Model):
    menu = models.ForeignKey(
        DailyMenu,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reject_logs'
    )

    date = models.DateField()
    reject_reason = models.TextField()

    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='menu_reject_logs'
    )

    rejected_at = models.DateTimeField(auto_now_add=True)

    created_by_username = models.CharField(max_length=150, blank=True)
    created_by_full_name = models.CharField(max_length=255, blank=True)

    menu_snapshot = models.TextField(blank=True)

    class Meta:
        ordering = ['-rejected_at']

    def __str__(self):
        return f"Từ chối menu {self.date}"
class WeeklyMenuDraft(models.Model):
    date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    dish_ids = models.JSONField(default=list)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('date',)
        ordering = ['date']

    def __str__(self):
        return f"Draft menu {self.date} - {self.created_by}"