"""Tạo file Excel báo cáo Tham gia + gửi qua NetChat DM.

Tách riêng khỏi views.py để dùng chung giữa endpoint download và endpoint
gửi NetChat (và sau này nếu có scheduled job).
"""

import io
import json
import re

import requests

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from accounts.models import UserProfile
from core.models import SystemConfig


KEY_RECIPIENTS = 'participation_export_recipients'
KEY_SEND_TIME = 'participation_export_send_time'


# ---------- Config trong SystemConfig ----------

def get_recipients():
    cfg = SystemConfig.objects.filter(key=KEY_RECIPIENTS).first()
    if not cfg or not cfg.value:
        return []
    try:
        data = json.loads(cfg.value)
        if isinstance(data, list):
            return [str(c).strip() for c in data if str(c).strip()]
    except (ValueError, TypeError):
        pass
    return []


def set_recipients(codes):
    cleaned = []
    seen = set()
    for c in codes:
        c = (c or '').strip()
        if c and c not in seen:
            seen.add(c)
            cleaned.append(c)
    SystemConfig.objects.update_or_create(
        key=KEY_RECIPIENTS,
        defaults={'value': json.dumps(cleaned, ensure_ascii=False)},
    )
    return cleaned


def get_send_time():
    cfg = SystemConfig.objects.filter(key=KEY_SEND_TIME).first()
    val = (cfg.value if cfg else '') or ''
    # Chỉ chấp nhận HH:MM, mặc định 13:00.
    if re.match(r'^\d{2}:\d{2}$', val):
        return val
    return '13:00'


def set_send_time(value):
    val = (value or '').strip()
    if not re.match(r'^\d{2}:\d{2}$', val):
        raise ValueError('Thời gian phải có dạng HH:MM (24h).')
    SystemConfig.objects.update_or_create(
        key=KEY_SEND_TIME,
        defaults={'value': val},
    )
    return val


# ---------- Build Excel ----------

def build_excel_bytes(target_date, rows):
    """Tạo file Excel binary từ rows. `rows` đến từ `_build_participation_rows`."""
    status_order = {'valid': 0, 'not_attended': 1, 'not_registered': 2}
    rows = sorted(rows, key=lambda r: (
        status_order.get(r['status'], 99),
        r['scan_time'] or 0,
        r['display_name'],
    ))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Tham gia'

    headers = ['STT', 'Họ và tên', 'Mã NV', 'Đơn vị', 'Phòng ban', 'Thời gian quét', 'Trạng thái', 'Loại']
    title = f'DANH SÁCH THAM GIA NGÀY {target_date.strftime("%d-%m-%Y")}'
    ws.merge_cells('A1:H1')
    ws['A1'] = title
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2563EB')
        cell.alignment = Alignment(horizontal='center', vertical='center')

    fills = {
        'valid': PatternFill('solid', fgColor='ECFDF5'),
        'not_attended': PatternFill('solid', fgColor='FEF2F2'),
        'not_registered': PatternFill('solid', fgColor='FFF7ED'),
    }

    for idx, r in enumerate(rows, start=1):
        excel_row = idx + 3
        profile = r.get('profile')
        unit = (profile.unit if profile else '') or ''
        dept = (profile.department if profile else '') or ''
        scan_str = r['scan_time'].strftime('%H:%M:%S') if r['scan_time'] else '—'
        values = [idx, r['display_name'], r['employee_code'], unit, dept, scan_str, r['status_label'], r['type']]
        fill = fills.get(r['status'])
        for col_idx, v in enumerate(values, start=1):
            cell = ws.cell(row=excel_row, column=col_idx, value=v)
            if fill:
                cell.fill = fill

    widths = [6, 28, 14, 24, 24, 16, 18, 14]
    for col_idx, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(ord('A') + col_idx - 1)].width = w

    summary_row = len(rows) + 5
    counts = {
        'valid': sum(1 for r in rows if r['status'] == 'valid'),
        'not_attended': sum(1 for r in rows if r['status'] == 'not_attended'),
        'not_registered': sum(1 for r in rows if r['status'] == 'not_registered'),
    }
    ws.cell(row=summary_row, column=1, value='Tổng:').font = Font(bold=True)
    ws.cell(row=summary_row, column=2, value=f"Đã điểm danh: {counts['valid']}")
    ws.cell(row=summary_row, column=3, value=f"Chưa điểm danh: {counts['not_attended']}")
    ws.cell(row=summary_row, column=4, value=f"Chưa đăng ký: {counts['not_registered']}")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------- Gửi qua NetChat DM ----------

def _get_netchat_config():
    url_cfg = SystemConfig.objects.filter(key='netchat_url').first()
    token_cfg = SystemConfig.objects.filter(key='netchat_token').first()
    if not url_cfg or not token_cfg:
        return None
    return {
        'url': url_cfg.value.strip().rstrip('/'),
        'token': token_cfg.value.strip(),
    }


def send_excel_to_recipients(target_date, file_bytes, recipient_codes):
    """Gửi file Excel qua DM NetChat cho danh sách MNV.

    Trả về dict {success: [...], failed: [(code, reason), ...]}.
    """
    cfg = _get_netchat_config()
    if not cfg:
        return {
            'success': [],
            'failed': [(c, 'Bot chưa được cấu hình URL/Token (vào Profile admin để thiết lập)') for c in recipient_codes],
        }

    headers = {
        'Authorization': f"Bearer {cfg['token']}",
        'User-Agent': 'curl/8.7.1',
    }

    # 1. Lấy bot_id
    try:
        r_me = requests.get(f"{cfg['url']}/api/v4/users/me", headers=headers, timeout=10)
        if r_me.status_code != 200:
            return {'success': [], 'failed': [(c, f'Bot không đăng nhập được: HTTP {r_me.status_code}') for c in recipient_codes]}
        bot_id = r_me.json().get('id')
    except requests.RequestException as e:
        return {'success': [], 'failed': [(c, f'Lỗi kết nối NetChat: {e}') for c in recipient_codes]}

    profiles = {
        (p.employee_code or '').strip(): p
        for p in UserProfile.objects.filter(employee_code__in=recipient_codes)
    }

    filename = f'tham_gia_{target_date.strftime("%Y-%m-%d")}.xlsx'
    success = []
    failed = []

    for code in recipient_codes:
        profile = profiles.get(code)
        if not profile or not profile.email:
            failed.append((code, 'Không tìm thấy tài khoản hoặc chưa có email'))
            continue

        username = profile.email.split('@')[0].strip().lower()
        try:
            r_user = requests.get(
                f"{cfg['url']}/api/v4/users/username/{username}",
                headers=headers, timeout=10
            )
            if r_user.status_code != 200:
                failed.append((code, 'Không tìm thấy user trên NetChat'))
                continue
            user_mm_id = r_user.json().get('id')

            r_chan = requests.post(
                f"{cfg['url']}/api/v4/channels/direct",
                headers={**headers, 'Content-Type': 'application/json'},
                json=[bot_id, user_mm_id], timeout=10
            )
            if r_chan.status_code not in (200, 201):
                failed.append((code, f'Không mở được kênh DM (HTTP {r_chan.status_code})'))
                continue
            channel_id = r_chan.json().get('id')

            # Upload file (multipart) — KHÔNG set Content-Type=json.
            files_payload = {
                'files': (filename, file_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            }
            r_file = requests.post(
                f"{cfg['url']}/api/v4/files",
                headers=headers,
                data={'channel_id': channel_id},
                files=files_payload,
                timeout=30,
            )
            if r_file.status_code not in (200, 201):
                failed.append((code, f'Upload file thất bại (HTTP {r_file.status_code})'))
                continue
            file_infos = r_file.json().get('file_infos') or []
            if not file_infos:
                failed.append((code, 'Mattermost không trả file_id'))
                continue
            file_id = file_infos[0].get('id')

            # Tạo post kèm file.
            message = f'📊 Báo cáo Tham gia ngày {target_date.strftime("%d-%m-%Y")}'
            r_post = requests.post(
                f"{cfg['url']}/api/v4/posts",
                headers={**headers, 'Content-Type': 'application/json'},
                json={'channel_id': channel_id, 'message': message, 'file_ids': [file_id]},
                timeout=10,
            )
            if r_post.status_code not in (200, 201):
                failed.append((code, f'Gửi post thất bại (HTTP {r_post.status_code})'))
                continue

            success.append(code)
        except requests.RequestException as e:
            failed.append((code, f'Lỗi mạng: {e}'))

    return {'success': success, 'failed': failed}
