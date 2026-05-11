"""
Management command: quét tin nhắn DM người dùng gửi cho bot NetChat.

Dùng cho cron / systemd timer:

    python manage.py poll_feedback

Tần suất khuyến nghị: 30 phút (production), 2 phút (test).
"""

from django.core.management.base import BaseCommand

from reviews.feedback_poller import poll_feedback


class Command(BaseCommand):
    help = 'Quét tin nhắn DM gửi cho bot NetChat và lưu vào FeedbackMessage.'

    def handle(self, *args, **options):
        result = poll_feedback()

        if result['error']:
            self.stderr.write(self.style.ERROR(f"❌ {result['error']}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"✅ Fetched={result['fetched']} Saved={result['saved']}"
        ))
