"""
Cảnh báo camera nhận diện TẮT trong giờ ăn trưa qua NetChat.

Chạy định kỳ mỗi phút (systemd timer). Nếu đang trong khung 11:03–12:30 (giờ VN)
mà camera nhận diện không gửi heartbeat (coi như tắt) thì gửi tin NetChat DM cho
user 'thanghv37'. Có cooldown chống spam (nhắc lại tối đa mỗi 2 phút khi vẫn tắt).

(Bắt đầu từ 11:03 vì client nhận diện 11:00 mới khởi động — chừa ~3 phút cho client
lên heartbeat lần đầu, tránh báo nhầm. Nhắc lại mỗi 2 phút để khi mất heartbeat
mình biết ngay, thay vì 30 phút quá lâu không kịp xử lý.)

Mọi tham số (khung giờ, người nhận, ngưỡng) FIX CỨNG theo yêu cầu — không cấu hình UI.
Cách chạy thủ công để test:
    python manage.py alert_camera_offline --force   # bỏ qua check giờ + cooldown
    python manage.py alert_camera_offline --test    # gửi 1 tin test ngay cho thanghv37
"""
from datetime import datetime, time, timedelta

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from core.models import RecognitionHeartbeat, SystemConfig

# ===== CẤU HÌNH FIX CỨNG =====
WINDOW_START = time(11, 3)        # 11:03 (client 11:00 mới khởi động, chừa ~3 phút lên heartbeat)
WINDOW_END = time(12, 30)         # 12:30
OFFLINE_SECONDS = 120            # > 2 phút không heartbeat => coi camera TẮT (tránh báo nhầm khi blip vài giây)
ALERT_COOLDOWN_MINUTES = 2       # khi vẫn tắt, nhắc lại mỗi 2 phút để biết ngay (30 phút quá lâu)
ALERT_USERNAME = 'thanghv37'     # user nhận cảnh báo
LAST_ALERT_KEY = 'camera_offline_alert_last_at'  # SystemConfig: thời điểm báo gần nhất


class Command(BaseCommand):
    help = 'Cảnh báo camera tắt trong khung 11:00-12:30 qua NetChat (gửi cho thanghv37).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Bỏ qua check khung giờ + cooldown; kiểm tra và gửi ngay nếu camera đang tắt.',
        )
        parser.add_argument(
            '--test', action='store_true',
            help='Gửi 1 tin test ngay cho thanghv37 (không cần camera tắt).',
        )

    def handle(self, *args, **options):
        force = options.get('force')
        now = timezone.localtime()

        if options.get('test'):
            ok, err = self._send_netchat(
                f"🔔 [TEST] Tin thử cảnh báo camera nhận diện — {now:%H:%M %d/%m/%Y}."
            )
            self.stdout.write(self.style.SUCCESS('Đã gửi tin test.') if ok
                              else self.style.ERROR(f'Gửi test thất bại: {err}'))
            return

        # 1. Chỉ chạy trong khung 11:00–12:30 (trừ khi --force)
        if not force and not (WINDOW_START <= now.time() <= WINDOW_END):
            return

        # 2. Camera có đang tắt không?
        offline, detail = self._camera_offline(now)
        if not offline:
            return

        # 3. Cooldown chống spam (trừ khi --force)
        if not force and not self._cooldown_passed(now):
            return

        # 4. Gửi cảnh báo
        msg = (
            "⚠️ CẢNH BÁO: Camera nhận diện đang TẮT trong giờ ăn trưa.\n"
            f"{detail}\n"
            f"Thời điểm kiểm tra: {now:%H:%M:%S %d/%m/%Y}.\n"
            "Vui lòng kiểm tra lại camera / hệ thống điểm danh."
        )
        ok, err = self._send_netchat(msg)
        if ok:
            SystemConfig.objects.update_or_create(
                key=LAST_ALERT_KEY, defaults={'value': now.isoformat()})
            self.stdout.write(self.style.SUCCESS(f'Đã gửi cảnh báo cho {ALERT_USERNAME}: {detail}'))
        else:
            self.stdout.write(self.style.ERROR(f'Gửi cảnh báo thất bại: {err}'))

    # ---------- Helpers ----------
    def _camera_offline(self, now):
        """Trả (offline: bool, detail: str). Coi là tắt nếu KHÔNG camera nào gửi
        heartbeat trong OFFLINE_SECONDS gần đây (hoặc chưa từng có heartbeat)."""
        heartbeats = list(RecognitionHeartbeat.objects.all())
        if not heartbeats:
            return True, "Chưa nhận được heartbeat nào từ camera."
        latest = max(hb.last_heartbeat_at for hb in heartbeats)
        elapsed = (now - latest).total_seconds()
        if elapsed >= OFFLINE_SECONDS:
            mins = int(elapsed // 60)
            return True, (f"Heartbeat gần nhất cách đây ~{mins} phút "
                          f"(lúc {timezone.localtime(latest):%H:%M:%S %d/%m}).")
        return False, ""

    def _cooldown_passed(self, now):
        cfg = SystemConfig.objects.filter(key=LAST_ALERT_KEY).first()
        if not cfg or not cfg.value:
            return True
        try:
            last = datetime.fromisoformat(cfg.value)
        except (ValueError, TypeError):
            return True
        return (now - last) >= timedelta(minutes=ALERT_COOLDOWN_MINUTES)

    def _resolve_netchat_username(self):
        """Username NetChat của người nhận: ưu tiên tra profile 'thanghv37' rồi lấy
        phần trước @ của email (đúng quy ước hệ thống); không có thì dùng luôn 'thanghv37'."""
        profile = (UserProfile.objects.filter(employee_code__iexact=ALERT_USERNAME).first()
                   or UserProfile.objects.filter(user__username__iexact=ALERT_USERNAME).first())
        if profile and profile.email:
            return profile.email.split('@')[0].strip().lower()
        return ALERT_USERNAME

    def _send_netchat(self, message):
        """Gửi DM NetChat cho người nhận. Trả (ok, error_msg)."""
        url_cfg = SystemConfig.objects.filter(key='netchat_url').first()
        token_cfg = SystemConfig.objects.filter(key='netchat_token').first()
        if not url_cfg or not token_cfg or not url_cfg.value or not token_cfg.value:
            return False, "Chưa cấu hình NetChat (netchat_url / netchat_token)."

        url = url_cfg.value.strip().rstrip('/')
        token = token_cfg.value.strip()
        username = self._resolve_netchat_username()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        }
        try:
            r_me = requests.get(f"{url}/api/v4/users/me", headers=headers, timeout=10)
            r_user = requests.get(f"{url}/api/v4/users/username/{username}", headers=headers, timeout=10)
            if r_me.status_code != 200 or r_user.status_code != 200:
                return False, (f"Không lấy được bot/user id "
                               f"(me={r_me.status_code}, user '{username}'={r_user.status_code}).")
            bot_id = r_me.json().get('id')
            user_mm_id = r_user.json().get('id')
            r_chan = requests.post(f"{url}/api/v4/channels/direct", headers=headers,
                                   json=[bot_id, user_mm_id], timeout=10)
            channel_id = r_chan.json().get('id')
            if not channel_id:
                return False, "Không tạo được kênh DM với người nhận."
            requests.post(f"{url}/api/v4/posts", headers=headers,
                          json={"channel_id": channel_id, "message": message}, timeout=10)
        except requests.RequestException as e:
            return False, f"Lỗi kết nối NetChat: {e}"
        return True, ""
