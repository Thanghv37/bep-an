from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import secrets
import re
import unicodedata


def slugify_vietnamese(text):
    text = unicodedata.normalize('NFD', text or '')
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def user_avatar_path(instance, filename):
    ext = filename.split('.')[-1].lower()

    employee_code = instance.employee_code or instance.user.username
    full_name = instance.full_name or instance.user.username
    name_slug = slugify_vietnamese(full_name)

    return f'user_avatars/{employee_code}_{name_slug}.{ext}'

class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_KITCHEN = 'kitchen'
    ROLE_DINER = 'diner'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_KITCHEN, 'Nhân viên bếp'),
        (ROLE_DINER, 'Người ăn'),
    ]

    GENDER_CHOICES = [
        ('Nam', 'Nam'),
        ('Nữ', 'Nữ'),
        ('Khác', 'Khác'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    employee_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Mã nhân viên'
    )

    full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Họ và tên'
    )

    email = models.EmailField(
        blank=True,
        verbose_name='Email'
    )

    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name='Giới tính'
    )

    unit = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Đơn vị'
    )

    department = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Phòng ban'
    )

    position = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Chức vụ'
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Số điện thoại'
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_DINER,
        verbose_name='Vai trò'
    )

    avatar = models.ImageField(
        upload_to=user_avatar_path,
        null=True,
        blank=True,
        verbose_name='Ảnh đại diện'
    )

    # OTP brute-force protection (TODO #2 audit). Khoá theo employee_code,
    # không theo IP vì là app nội bộ. Chỉ chặn verify, không chặn request.
    otp_failed_attempts = models.PositiveSmallIntegerField(default=0)
    otp_locked_until = models.DateTimeField(null=True, blank=True)
    otp_last_sent_at = models.DateTimeField(null=True, blank=True)

    OTP_MAX_FAILED = 10
    OTP_LOCK_MINUTES = 15
    OTP_RESEND_COOLDOWN_SECONDS = 60

    class Meta:
        verbose_name = 'Thông tin người dùng'
        verbose_name_plural = 'Thông tin người dùng'

    def __str__(self):
        display_name = self.full_name or self.user.username
        return f'{display_name} - {self.get_role_display()}'

    def is_otp_locked(self):
        return bool(self.otp_locked_until and self.otp_locked_until > timezone.now())

    def otp_lock_seconds_remaining(self):
        if not self.is_otp_locked():
            return 0
        return int((self.otp_locked_until - timezone.now()).total_seconds())

    def otp_resend_seconds_remaining(self):
        if not self.otp_last_sent_at:
            return 0
        elapsed = (timezone.now() - self.otp_last_sent_at).total_seconds()
        remaining = self.OTP_RESEND_COOLDOWN_SECONDS - elapsed
        return max(0, int(remaining))

    def register_otp_failure(self):
        self.otp_failed_attempts = (self.otp_failed_attempts or 0) + 1
        if self.otp_failed_attempts >= self.OTP_MAX_FAILED:
            self.otp_locked_until = timezone.now() + timedelta(minutes=self.OTP_LOCK_MINUTES)
        self.save(update_fields=['otp_failed_attempts', 'otp_locked_until'])

    def reset_otp_attempts(self):
        self.otp_failed_attempts = 0
        self.otp_locked_until = None
        self.save(update_fields=['otp_failed_attempts', 'otp_locked_until'])

    def mark_otp_sent(self):
        self.otp_last_sent_at = timezone.now()
        self.save(update_fields=['otp_last_sent_at'])


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserProfile.ROLE_ADMIN if instance.is_superuser else UserProfile.ROLE_DINER

        UserProfile.objects.create(
            user=instance,
            role=role,
            employee_code=instance.username,
            full_name=instance.get_full_name() or instance.username,
            email=instance.email or '',
        )
    else:
        profile, _ = UserProfile.objects.get_or_create(user=instance)

        if instance.email and not profile.email:
            profile.email = instance.email
            profile.save(update_fields=['email'])
class OTPToken(models.Model):
    employee_code = models.CharField(max_length=50)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Tự động tính thời gian hết hạn là 10 phút kể từ lúc tạo
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        # Kiểm tra mã còn hạn và chưa dùng hay không
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.employee_code} - {self.otp_code}"