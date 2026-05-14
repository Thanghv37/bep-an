"""Management command: tự động gửi báo cáo Tham gia qua NetChat DM.

Chạy qua systemd timer `participation-report.timer` (mỗi 1 phút). Command check:
  - Có recipient cấu hình chưa?
  - Giờ:phút hiện tại (theo timezone VN) có khớp send_time đã cấu hình?
  - Hôm nay đã gửi chưa? (idempotent qua key SystemConfig `participation_export_last_sent_date`)

Cờ `--force` bỏ qua check thời gian + last_sent (để admin test thủ công).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import SystemConfig
from registrations.participation_export import (
    build_excel_bytes,
    get_recipients,
    get_send_time,
    send_excel_to_recipients,
)


KEY_LAST_SENT = 'participation_export_last_sent_date'


class Command(BaseCommand):
    help = 'Auto-send báo cáo Tham gia qua NetChat DM theo lịch cấu hình.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Bỏ qua check thời gian và last_sent_date, gửi ngay.',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        # 1. Check recipient
        recipients = get_recipients()
        if not recipients:
            self.stdout.write('[skip] No recipients configured.')
            return

        now_vn = timezone.localtime()
        today_str = now_vn.date().isoformat()

        if not force:
            # 2. Check khớp send_time (HH:MM)
            send_time = get_send_time()
            try:
                send_h, send_m = map(int, send_time.split(':'))
            except (ValueError, AttributeError):
                self.stderr.write(f'[err] send_time không hợp lệ: "{send_time}"')
                return

            if not (now_vn.hour == send_h and now_vn.minute == send_m):
                # Không log để journalctl đỡ spam (chạy mỗi phút).
                return

            # 3. Check đã gửi hôm nay chưa
            last_cfg = SystemConfig.objects.filter(key=KEY_LAST_SENT).first()
            if last_cfg and last_cfg.value == today_str:
                self.stdout.write(f'[skip] Already sent today ({today_str}).')
                return

        # 4. Build Excel + gửi
        # Import muộn để tránh circular import lúc Django startup.
        from registrations.views import _build_participation_rows

        target_date = now_vn.date()
        rows = _build_participation_rows(target_date)
        file_bytes = build_excel_bytes(target_date, rows)

        self.stdout.write(f'[run] Sending report for {target_date} to {len(recipients)} recipient(s)...')
        result = send_excel_to_recipients(target_date, file_bytes, recipients)

        # 5. Chỉ mark last_sent nếu thành công (≥1 người nhận được).
        # Nếu fail hết → lần fire kế tiếp thử lại.
        if result['success']:
            SystemConfig.objects.update_or_create(
                key=KEY_LAST_SENT,
                defaults={'value': today_str},
            )
            self.stdout.write(self.style.SUCCESS(
                f'[ok] Sent {len(result["success"])}/{len(recipients)} recipient(s).'
            ))

        if result['failed']:
            for code, reason in result['failed']:
                self.stderr.write(f'[fail] {code}: {reason.encode("ascii", "replace").decode("ascii")}')
