"""
Polling logic cho FeedbackMessage.

Quét các DM channel của bot trên NetChat (Mattermost), lấy post mới từ user
gửi cho bot, lưu vào bảng `FeedbackMessage`.

Được gọi bởi management command `poll_feedback` (cron systemd timer).
"""

import logging
import time
from datetime import datetime, timezone

import requests

from accounts.models import UserProfile
from core.models import SystemConfig

from .models import FeedbackMessage


logger = logging.getLogger(__name__)


KEY_LAST_POLL_TS = 'feedback_last_poll_ts'  # ms timestamp của post mới nhất đã thấy

REQUEST_TIMEOUT = 15

HEADERS_TEMPLATE = {
    "Content-Type": "application/json",
    "User-Agent": "curl/8.7.1",  # vượt firewall, giống code OTP đang dùng
}


def _get_netchat_config():
    """Lấy URL và Token bot từ SystemConfig. Trả về None nếu chưa cấu hình."""
    url_cfg = SystemConfig.objects.filter(key='netchat_url').first()
    token_cfg = SystemConfig.objects.filter(key='netchat_token').first()
    if not url_cfg or not token_cfg or not url_cfg.value or not token_cfg.value:
        return None, None
    return url_cfg.value.strip().rstrip('/'), token_cfg.value.strip()


def _build_headers(token):
    headers = dict(HEADERS_TEMPLATE)
    headers['Authorization'] = f'Bearer {token}'
    return headers


def _get_last_poll_ts():
    """Lấy timestamp (ms) của lần poll gần nhất. Lần đầu trả về `None`."""
    cfg = SystemConfig.objects.filter(key=KEY_LAST_POLL_TS).first()
    if cfg and cfg.value:
        try:
            return int(cfg.value)
        except (TypeError, ValueError):
            return None
    return None


def _save_last_poll_ts(ts_ms):
    SystemConfig.objects.update_or_create(
        key=KEY_LAST_POLL_TS,
        defaults={'value': str(ts_ms)},
    )


def _build_employee_lookup():
    """Map username (phần trước @ trong email) -> (employee_code, full_name)."""
    lookup = {}
    profiles = UserProfile.objects.exclude(email='').only(
        'email', 'employee_code', 'full_name'
    )
    for p in profiles:
        username = (p.email or '').split('@')[0].strip().lower()
        if username:
            lookup[username] = (p.employee_code, p.full_name)
    return lookup


def poll_feedback():
    """Chạy 1 lần poll. Trả về dict {fetched: int, saved: int, error: str|None}."""
    netchat_url, token = _get_netchat_config()
    if not netchat_url:
        msg = 'Chưa cấu hình NetChat URL/Token trong Profile admin.'
        logger.warning('[poll_feedback] %s', msg)
        return {'fetched': 0, 'saved': 0, 'error': msg}

    headers = _build_headers(token)

    try:
        # 1. Lấy ID của bot
        r_me = requests.get(
            f'{netchat_url}/api/v4/users/me',
            headers=headers, timeout=REQUEST_TIMEOUT,
        )
        if r_me.status_code != 200:
            err = f'Không lấy được bot ID: {r_me.status_code}'
            logger.error('[poll_feedback] %s', err)
            return {'fetched': 0, 'saved': 0, 'error': err}
        bot_id = r_me.json().get('id')

        # 2. Lấy danh sách channel mà bot là member (bao gồm DM)
        r_channels = requests.get(
            f'{netchat_url}/api/v4/users/{bot_id}/channels',
            headers=headers, timeout=REQUEST_TIMEOUT,
        )
        if r_channels.status_code != 200:
            err = f'Không lấy được channels: {r_channels.status_code}'
            logger.error('[poll_feedback] %s', err)
            return {'fetched': 0, 'saved': 0, 'error': err}

        all_channels = r_channels.json()
        # DM channel có type='D'
        dm_channels = [c for c in all_channels if c.get('type') == 'D']

        last_poll_ts = _get_last_poll_ts()
        # Lần đầu tiên: bắt đầu từ now (không kéo lịch sử)
        if last_poll_ts is None:
            last_poll_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
            _save_last_poll_ts(last_poll_ts)
            logger.info('[poll_feedback] First run, baseline=%s', last_poll_ts)
            return {'fetched': 0, 'saved': 0, 'error': None}

        # OPTIMIZATION: chỉ poll channel có post mới hơn baseline.
        # Mattermost cung cấp `last_post_at` (ms) cho mỗi channel — dùng để filter
        # giảm số API call → tránh rate limit 429 khi bot có nhiều DM.
        active_channels = [
            c for c in dm_channels
            if c.get('last_post_at', 0) > last_poll_ts
        ]
        logger.info(
            '[poll_feedback] DM total=%d, active (có post mới)=%d',
            len(dm_channels), len(active_channels),
        )

        employee_lookup = _build_employee_lookup()

        # User cache để tránh gọi /users/{id} nhiều lần cho cùng 1 user
        user_info_cache = {}

        fetched = 0
        saved = 0
        max_seen_ts = last_poll_ts

        for ch in active_channels:
            channel_id = ch['id']

            # Throttle nhẹ giữa các call để tránh rate-limit 429
            time.sleep(0.2)

            r_posts = requests.get(
                f'{netchat_url}/api/v4/channels/{channel_id}/posts',
                headers=headers,
                params={'since': last_poll_ts},
                timeout=REQUEST_TIMEOUT,
            )
            if r_posts.status_code == 429:
                # Mattermost yêu cầu chậm lại — nghỉ 5s rồi thử lại 1 lần
                logger.warning('[poll_feedback] Rate limited, sleep 5s rồi retry...')
                time.sleep(5)
                r_posts = requests.get(
                    f'{netchat_url}/api/v4/channels/{channel_id}/posts',
                    headers=headers,
                    params={'since': last_poll_ts},
                    timeout=REQUEST_TIMEOUT,
                )
            if r_posts.status_code != 200:
                logger.warning(
                    '[poll_feedback] Lỗi GET posts channel=%s status=%s',
                    channel_id, r_posts.status_code,
                )
                continue

            data = r_posts.json()
            posts = data.get('posts', {})

            for post_id, post in posts.items():
                fetched += 1

                # Bỏ qua tin nhắn của chính bot
                if post.get('user_id') == bot_id:
                    continue

                # Bỏ qua post system (join/leave channel...)
                if post.get('type'):  # post thường có type='', system post có type khác
                    continue

                msg_text = (post.get('message') or '').strip()
                if not msg_text:
                    continue

                create_at = post.get('create_at')  # ms
                if create_at and create_at > max_seen_ts:
                    max_seen_ts = create_at

                # Lookup info của sender
                sender_id = post.get('user_id')
                if sender_id not in user_info_cache:
                    time.sleep(0.1)
                    r_user = requests.get(
                        f'{netchat_url}/api/v4/users/{sender_id}',
                        headers=headers, timeout=REQUEST_TIMEOUT,
                    )
                    if r_user.status_code == 200:
                        u = r_user.json()
                        user_info_cache[sender_id] = {
                            'username': u.get('username', ''),
                            'full_name': (
                                f'{u.get("first_name", "")} {u.get("last_name", "")}'
                                .strip() or u.get('nickname', '')
                            ),
                        }
                    else:
                        user_info_cache[sender_id] = {'username': sender_id, 'full_name': ''}

                info = user_info_cache[sender_id]
                username = info['username']
                # Nếu UserProfile có user này (theo email), dùng employee_code + full_name từ DB
                emp_code, profile_full_name = employee_lookup.get(
                    username.lower(), ('', '')
                )

                _, created = FeedbackMessage.objects.get_or_create(
                    mattermost_post_id=post_id,
                    defaults={
                        'channel_id': channel_id,
                        'sender_username': username,
                        'sender_full_name': profile_full_name or info['full_name'],
                        'employee_code': emp_code,
                        'message': msg_text,
                        'posted_at': datetime.fromtimestamp(
                            create_at / 1000, tz=timezone.utc
                        ) if create_at else datetime.now(timezone.utc),
                    },
                )
                if created:
                    saved += 1

        if max_seen_ts > last_poll_ts:
            _save_last_poll_ts(max_seen_ts)

        logger.info(
            '[poll_feedback] Done. fetched=%d saved=%d channels=%d',
            fetched, saved, len(dm_channels),
        )
        return {'fetched': fetched, 'saved': saved, 'error': None}

    except requests.RequestException as e:
        logger.exception('[poll_feedback] Network error')
        return {'fetched': 0, 'saved': 0, 'error': f'Lỗi network: {e}'}
    except Exception as e:
        logger.exception('[poll_feedback] Unexpected error')
        return {'fetched': 0, 'saved': 0, 'error': f'Lỗi: {e}'}
