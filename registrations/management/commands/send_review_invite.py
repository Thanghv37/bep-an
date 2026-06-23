"""Gửi tin MỜI ĐÁNH GIÁ qua NetChat cho người đã ăn trưa (mặc định 13h).

Chạy mỗi phút qua systemd timer `review-invite.timer`. Mỗi lần check:
  - Tính năng có đang BẬT không? (cấu hình trong trang Tham gia → ⚙ Cài đặt)
  - Giờ:phút hiện tại (giờ VN) có khớp giờ gửi đã cấu hình không?
  - Hôm nay có nằm trong các ngày gửi (dùng chung send_days với báo cáo Tham gia)?
  - Hôm nay đã gửi chưa? (idempotent qua SystemConfig `review_invite_last_sent_date`)

Người nhận = những người ĐÃ ĐIỂM DANH hôm nay (AttendanceLog) và có hồ sơ + email.
Gửi DM kèm link đánh giá, throttle 15 tin / 60s để tránh rate-limit của bot.

Cờ `--force` bỏ qua mọi check (bật/tắt, giờ, ngày, last_sent) — để admin test tay.
"""
import time as time_module

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from core.models import AttendanceLog, SystemConfig
from core.message_templates import get_review_invite_template, render_template
from registrations.participation_export import (
    get_review_invite_enabled,
    get_review_invite_send_time,
    get_send_days,
)

KEY_LAST_SENT = 'review_invite_last_sent_date'
THROTTLE_EVERY = 15      # cứ 15 tin gửi đi thì nghỉ
THROTTLE_SLEEP = 60      # nghỉ 60s


class Command(BaseCommand):
    help = 'Gửi tin mời đánh giá cho người đã ăn trưa (mặc định 13h) qua NetChat.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Bỏ qua check bật/tắt, giờ, ngày, last_sent — gửi ngay.',
        )

    def handle(self, *args, **options):
        force = options.get('force')
        now_vn = timezone.localtime()
        today = now_vn.date()
        today_str = today.isoformat()

        if not force:
            if not get_review_invite_enabled():
                return  # tắt → im lặng (chạy mỗi phút, không spam log)

            send_time = get_review_invite_send_time()
            try:
                send_h, send_m = map(int, send_time.split(':'))
            except (ValueError, AttributeError):
                self.stderr.write(f'[err] Giờ gửi không hợp lệ: "{send_time}"')
                return
            if not (now_vn.hour == send_h and now_vn.minute == send_m):
                return

            if today.weekday() not in get_send_days():
                self.stdout.write(f'[skip] Hôm nay (weekday={today.weekday()}) không nằm trong send_days.')
                return

            last_cfg = SystemConfig.objects.filter(key=KEY_LAST_SENT).first()
            if last_cfg and last_cfg.value == today_str:
                self.stdout.write(f'[skip] Đã gửi tin mời hôm nay ({today_str}).')
                return

        # Người đã điểm danh hôm nay (đã ăn) — distinct mã NV.
        attended_codes = sorted({
            (c or '').strip()
            for c in AttendanceLog.objects.filter(
                scan_time__date=today
            ).values_list('employee_code', flat=True)
            if c and c.strip()
        })
        if not attended_codes:
            self.stdout.write('[skip] Chưa có ai điểm danh hôm nay.')
            return

        # Đánh dấu đã gửi NGAY (trước vòng gửi dài ~chục phút) để lần fire kế tiếp
        # không gửi trùng. Mass-send: tránh gửi trùng quan trọng hơn auto-retry.
        SystemConfig.objects.update_or_create(
            key=KEY_LAST_SENT, defaults={'value': today_str})

        sent, failed = self._send_all(today, attended_codes)
        self.stdout.write(self.style.SUCCESS(
            f'[ok] Tin mời {today_str}: gửi {sent}/{len(attended_codes)} (lỗi {failed}).'))

    # ---------- Gửi ----------
    def _netchat(self):
        url_cfg = SystemConfig.objects.filter(key='netchat_url').first()
        token_cfg = SystemConfig.objects.filter(key='netchat_token').first()
        if not url_cfg or not token_cfg or not url_cfg.value or not token_cfg.value:
            return None
        return url_cfg.value.strip().rstrip('/'), token_cfg.value.strip()

    def _send_all(self, today, codes):
        cfg = self._netchat()
        if not cfg:
            self.stderr.write('[err] Chưa cấu hình NetChat (netchat_url / netchat_token).')
            return 0, len(codes)
        url, token = cfg
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'curl/8.7.1',
        }
        try:
            r_me = requests.get(f'{url}/api/v4/users/me', headers=headers, timeout=10)
            if r_me.status_code != 200:
                self.stderr.write(f'[err] Bot không đăng nhập được: HTTP {r_me.status_code}')
                return 0, len(codes)
            bot_id = r_me.json().get('id')
        except requests.RequestException as e:
            self.stderr.write(f'[err] Lỗi kết nối NetChat: {e}')
            return 0, len(codes)

        # Dữ liệu chung cho cả lô.
        from registrations.views import _build_review_link, _build_menu_summary
        review_link = _build_review_link()
        menu_summary = _build_menu_summary(today)
        formatted_date = today.strftime('%d-%m-%Y')
        template = get_review_invite_template()

        profiles = {
            (p.employee_code or '').strip(): p
            for p in UserProfile.objects.filter(employee_code__in=codes)
        }

        sent = 0
        failed = 0
        attempt = 0
        for code in codes:
            profile = profiles.get(code)
            if not profile or not profile.email:
                # Không có tài khoản NetChat (khách ngoài / chưa có hồ sơ) → bỏ qua.
                failed += 1
                continue

            if attempt > 0 and attempt % THROTTLE_EVERY == 0:
                time_module.sleep(THROTTLE_SLEEP)
            attempt += 1

            message = render_template(
                template,
                full_name=profile.full_name or code,
                employee_code=code,
                target_date=formatted_date,
                menu_summary=menu_summary,
                review_link=review_link,
            )
            if self._send_one(url, headers, bot_id, profile.email, message):
                sent += 1
            else:
                failed += 1
        return sent, failed

    def _send_one(self, url, headers, bot_id, email, message):
        username = email.split('@')[0].strip().lower()
        try:
            r_user = requests.get(
                f'{url}/api/v4/users/username/{username}', headers=headers, timeout=10)
            if r_user.status_code != 200:
                return False
            user_id = r_user.json().get('id')
            if not user_id:
                return False
            r_chan = requests.post(
                f'{url}/api/v4/channels/direct', headers=headers,
                json=[bot_id, user_id], timeout=10)
            if r_chan.status_code not in (200, 201):
                return False
            channel_id = r_chan.json().get('id')
            if not channel_id:
                return False
            r_post = requests.post(
                f'{url}/api/v4/posts', headers=headers,
                json={'channel_id': channel_id, 'message': message}, timeout=10)
            return r_post.status_code in (200, 201)
        except requests.RequestException:
            return False
