"""Gửi NetChat DM thông báo cho người chuyển/nhận khi transfer thay đổi trạng thái.

Tách module riêng để meal_transfer.py không phải import requests trực tiếp,
và để dễ tắt noti khi test.
"""
import logging

import requests

from accounts.models import UserProfile
from .participation_export import _get_netchat_config


logger = logging.getLogger(__name__)


def _lookup_mm_user(cfg, headers, email):
    """Tìm Mattermost user qua email (NetChat lookup-by-email không phân biệt case)."""
    if not email:
        return None
    try:
        r = requests.get(
            f"{cfg['url']}/api/v4/users/email/{email.lower()}",
            headers=headers, timeout=10,
        )
        if r.status_code == 200:
            return r.json().get('id')
    except requests.RequestException as e:
        logger.warning('NetChat lookup email %s lỗi: %s', email, e)
    return None


def _send_dm(cfg, headers, bot_id, user_mm_id, message):
    try:
        r_chan = requests.post(
            f"{cfg['url']}/api/v4/channels/direct",
            headers={**headers, 'Content-Type': 'application/json'},
            json=[bot_id, user_mm_id], timeout=10,
        )
        if r_chan.status_code not in (200, 201):
            return False
        channel_id = r_chan.json().get('id')
        r_post = requests.post(
            f"{cfg['url']}/api/v4/posts",
            headers={**headers, 'Content-Type': 'application/json'},
            json={'channel_id': channel_id, 'message': message}, timeout=10,
        )
        return r_post.status_code in (200, 201)
    except requests.RequestException as e:
        logger.warning('NetChat send DM lỗi: %s', e)
        return False


def _build_messages(transfer, event, transferred_keys=None, conflict_keys=None):
    """Trả về list [(emp_code, message_string), ...] các tin cần gửi.

    Một emp_code có thể xuất hiện nhiều lần khi 1 ngày có nhiều bữa được chuyển
    (mỗi bữa 1 tin riêng để dễ đọc).

    event:
    - 'pending': A bấm chuyển nhưng chưa có data -> chỉ A nhận tin ghi nhận.
    - 'applied': áp dụng thành công -> A + B nhận 1 tin cho mỗi (meal, kitchen).
    - 'failed_a_not_registered': hết hạn mà A không có đăng ký -> A + B nhận.
    - 'failed_b_conflict': B đã có đăng ký trùng -> A + B nhận 1 tin/conflict.
    - 'cancelled': user/admin tự hủy -> A + B nhận (giữ cho luồng manual cancel).
    """
    date_str = transfer.meal_date.strftime('%d/%m/%Y')
    from_name = transfer.from_full_name or transfer.from_employee_code
    to_name = transfer.to_full_name or transfer.to_employee_code
    msgs = []

    if event == 'pending':
        msgs.append((
            transfer.from_employee_code,
            f'📝 Đã ghi nhận yêu cầu chuyển suất ăn ngày {date_str} '
            f'cho đồng chí {to_name}. Hệ thống sẽ tự áp dụng khi data đăng ký '
            f'được nhập (trước 11h ngày {date_str}).'
        ))
        return msgs

    if event == 'applied':
        # 1 tin cho mỗi (meal, kitchen) đã chuyển.
        for meal, kitchen in (transferred_keys or [('', '')]):
            meal_disp = meal or 'suất ăn'
            kitchen_disp = kitchen or '(chưa rõ bếp)'
            msg = (
                f'✅ Đồng chí {from_name} đã chuyển suất ăn "{meal_disp}" '
                f'ngày {date_str} cho đồng chí {to_name} tại "{kitchen_disp}".'
            )
            msgs.append((transfer.from_employee_code, msg))
            msgs.append((transfer.to_employee_code, msg))
        return msgs

    if event == 'failed_a_not_registered':
        # A không có đăng ký -> không có meal/kitchen cụ thể.
        msg = (
            f'❌ Đồng chí {from_name} chuyển suất ăn ngày {date_str} '
            f'cho đồng chí {to_name} không thành công. '
            f'Lý do: đồng chí {from_name} chưa đăng ký suất ăn ngày {date_str}.'
        )
        msgs.append((transfer.from_employee_code, msg))
        msgs.append((transfer.to_employee_code, msg))
        return msgs

    if event == 'failed_b_conflict':
        # 1 tin cho mỗi (meal, kitchen) bị trùng.
        for meal, kitchen in (conflict_keys or [('', '')]):
            meal_disp = meal or 'suất ăn'
            kitchen_disp = kitchen or '(chưa rõ bếp)'
            msg = (
                f'❌ Đồng chí {from_name} chuyển suất ăn "{meal_disp}" '
                f'ngày {date_str} cho đồng chí {to_name} tại "{kitchen_disp}" '
                f'không thành công. Lý do: đồng chí {to_name} đã đăng ký suất ăn '
                f'"{meal_disp}" ngày {date_str} tại "{kitchen_disp}".'
            )
            msgs.append((transfer.from_employee_code, msg))
            msgs.append((transfer.to_employee_code, msg))
        return msgs

    if event == 'cancelled':
        reason = transfer.cancel_reason or 'không rõ lý do'
        msg_from = (
            f'❌ Yêu cầu chuyển suất ăn ngày {date_str} cho đồng chí {to_name} '
            f'đã bị hủy. Lý do: {reason}'
        )
        msg_to = (
            f'ℹ Yêu cầu chuyển suất ăn ngày {date_str} từ đồng chí {from_name} '
            f'đã bị hủy. Lý do: {reason}'
        )
        msgs.append((transfer.from_employee_code, msg_from))
        msgs.append((transfer.to_employee_code, msg_to))
        return msgs

    return msgs


def send_transfer_netchat(transfer, event, transferred_keys=None, conflict_keys=None):
    """Gửi DM cho người liên quan khi transfer chuyển trạng thái.

    event: xem docstring _build_messages.
    Lỗi mạng / config thiếu -> nuốt, log warning. KHÔNG raise.
    """
    msgs = _build_messages(
        transfer, event,
        transferred_keys=transferred_keys,
        conflict_keys=conflict_keys,
    )
    if not msgs:
        return

    cfg = _get_netchat_config()
    if not cfg:
        logger.info('NetChat chưa cấu hình, bỏ qua noti transfer %s', transfer.pk)
        return

    headers = {
        'Authorization': f"Bearer {cfg['token']}",
        'User-Agent': 'curl/8.7.1',
    }
    try:
        r_me = requests.get(f"{cfg['url']}/api/v4/users/me", headers=headers, timeout=10)
        if r_me.status_code != 200:
            logger.warning('NetChat bot login fail (HTTP %s)', r_me.status_code)
            return
        bot_id = r_me.json().get('id')
    except requests.RequestException as e:
        logger.warning('NetChat bot login lỗi: %s', e)
        return

    # Gom theo emp_code để 1 user chỉ lookup NetChat 1 lần, dù có nhiều tin.
    by_code = {}
    for code, message in msgs:
        by_code.setdefault(code, []).append(message)

    profiles = {
        (p.employee_code or '').strip(): p
        for p in UserProfile.objects.filter(employee_code__in=list(by_code.keys()))
    }
    for code, message_list in by_code.items():
        profile = profiles.get(code)
        if not profile or not profile.email:
            logger.info('Bỏ qua noti %s — chưa có profile/email', code)
            continue
        user_mm_id = _lookup_mm_user(cfg, headers, profile.email)
        if not user_mm_id:
            logger.info('Bỏ qua noti %s — không tìm thấy user NetChat', code)
            continue
        for message in message_list:
            ok = _send_dm(cfg, headers, bot_id, user_mm_id, message)
            if not ok:
                logger.warning('Gửi noti transfer %s tới %s thất bại', transfer.pk, code)
