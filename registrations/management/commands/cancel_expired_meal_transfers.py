"""Cancel các yêu cầu chuyển suất ăn pending đã quá 11h ngày X.

Chạy thủ công:
    python manage.py cancel_expired_meal_transfers

Hoặc setup cron/timer chạy mỗi 30 phút (tùy mức độ realtime mong muốn).
"""
from django.core.management.base import BaseCommand

from registrations.meal_transfer import cancel_expired_transfers


class Command(BaseCommand):
    help = 'Hủy các yêu cầu chuyển suất ăn pending đã quá 11h ngày suất ăn.'

    def handle(self, *args, **options):
        n = cancel_expired_transfers()
        if n:
            self.stdout.write(self.style.SUCCESS(f'Đã hủy {n} yêu cầu hết hạn.'))
        else:
            self.stdout.write('Không có yêu cầu nào hết hạn.')
