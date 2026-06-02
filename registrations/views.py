from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.db.models import Sum
from accounts.models import UserProfile
from accounts.permissions import can_manage_menu, is_admin
from .forms import STATUS_FIXED
from .import_utils import import_registrations_from_excel
from .models import MealRegistration
from .options import (
    get_meal_options,
    get_kitchen_options,
    set_meal_options,
    set_kitchen_options,
)
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from core.models import AttendanceLog, AttendanceCapture
from django.utils.timezone import now
import threading
import time
import requests
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.models import UserProfile
from .models import MealRegistration, NotificationLog
from core.models import SystemConfig  # Import bảng cấu hình Bot của bạn nếu có


@login_required
@user_passes_test(can_manage_menu)
def registration_list(request):
    selected_date_str = request.GET.get('date')
    keyword = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    meal_filter = request.GET.get('meal', '').strip()
    kitchen_filter = request.GET.get('kitchen', '').strip()

    if selected_date_str:
        try:
            selected_date = date.fromisoformat(selected_date_str)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    registrations = MealRegistration.objects.filter(date=selected_date)
    total_quantity = registrations.aggregate(
        total=Sum('quantity')
    )['total'] or 0
    if keyword:
        registrations = registrations.filter(
            Q(employee_code__icontains=keyword) |
            Q(full_name__icontains=keyword)
        )

    if status_filter:
        registrations = registrations.filter(status=status_filter)

    if meal_filter:
        registrations = registrations.filter(meal_name=meal_filter)

    if kitchen_filter:
        registrations = registrations.filter(kitchen_name=kitchen_filter)

    employee_codes = list(registrations.values_list('employee_code', flat=True))

    profiles = UserProfile.objects.filter(employee_code__in=employee_codes)
    profile_map = {p.employee_code: p for p in profiles}

    rows = []
    for item in registrations.order_by('employee_code'):
        rows.append({
            'registration': item,
            'profile': profile_map.get(item.employee_code),
        })

    # Người chưa có hồ sơ (đơn vị khác) lên đầu, sau đó MNV tăng dần trong mỗi nhóm.
    rows.sort(key=lambda r: (r['profile'] is not None, r['registration'].employee_code or ''))

    status_choices = MealRegistration.objects.exclude(status='').values_list(
        'status', flat=True
    ).distinct().order_by('status')

    meal_choices = MealRegistration.objects.exclude(meal_name='').values_list(
        'meal_name', flat=True
    ).distinct().order_by('meal_name')

    kitchen_choices = MealRegistration.objects.exclude(kitchen_name='').values_list(
        'kitchen_name', flat=True
    ).distinct().order_by('kitchen_name')

    # Job gửi tin báo cơm đang chạy ngầm? → truyền remaining + total để JS restore countdown.
    notif_remaining = 0
    notif_total = 0
    cfg_until = SystemConfig.objects.filter(key='notification_job_active_until').first()
    if cfg_until and cfg_until.value:
        try:
            active_until = datetime.fromisoformat(cfg_until.value)
            delta = (active_until - now()).total_seconds()
            if delta > 0:
                notif_remaining = int(delta)
                cfg_total = SystemConfig.objects.filter(key='notification_job_total').first()
                if cfg_total and cfg_total.value.isdigit():
                    notif_total = int(cfg_total.value)
        except (ValueError, TypeError):
            pass

    return render(request, 'registrations/registration_list.html', {
        'rows': rows,
        'selected_date': selected_date,
        'keyword': keyword,
        'status_filter': status_filter,
        'meal_filter': meal_filter,
        'kitchen_filter': kitchen_filter,
        'status_choices': status_choices,
        'notification_remaining_seconds': notif_remaining,
        'notification_total_count': notif_total,
        'meal_choices': meal_choices,
        'kitchen_choices': kitchen_choices,
        'total_quantity': total_quantity,
    })


@login_required
@user_passes_test(can_manage_menu)
def registration_import(request):
    if request.method != 'POST':
        return redirect('registration_list')

    file = request.FILES.get('file')

    if not file:
        messages.error(request, 'Bạn chưa chọn file Excel.')
        return redirect('registration_list')

    created, updated, errors = import_registrations_from_excel(file)

    messages.success(
        request,
        f'Import thành công: {created} tạo mới, {updated} cập nhật.'
    )

    if errors:
        messages.warning(request, 'Có lỗi khi import:')
        for err in errors[:10]:
            messages.warning(request, err)

    # Sau khi có data đăng ký mới, apply các yêu cầu chuyển suất đang chờ.
    try:
        from .meal_transfer import apply_all_pending_transfers
        result = apply_all_pending_transfers()
        if result['applied']:
            messages.success(
                request,
                f'Đã áp dụng {result["applied"]} yêu cầu chuyển suất ăn đang chờ.'
            )
    except Exception as e:
        messages.warning(request, f'Không áp dụng được yêu cầu chuyển suất: {e}')

    return redirect('registration_list')


def _default_meal_kitchen(meal_options, kitchen_options):
    """Bữa ăn / bếp ăn đề xuất sẵn — tìm trong option đã cấu hình theo từ khóa
    ('trưa' / 'khu vực 2') nên khớp đúng string option dù có hậu tố gì."""
    meal = next((o for o in meal_options if 'trưa' in o.lower()), '')
    kitchen = next((o for o in kitchen_options if 'khu vực 2' in o.lower()), '')
    return meal, kitchen


@login_required
@user_passes_test(can_manage_menu)
def registration_create(request):
    """Thêm đăng kí suất ăn thủ công — hỗ trợ nhập NHIỀU người cùng lúc.

    Ngày / Bữa ăn / Bếp ăn dùng chung cho cả lô; mỗi người là 1 dòng
    (mã NV + số suất). Nếu có bất kỳ dòng nào sai → không lưu gì cả,
    render lại form kèm lỗi từng dòng (giữ nguyên dữ liệu đã nhập).
    """
    meal_options = get_meal_options()
    kitchen_options = get_kitchen_options()

    # Dict {employee_code: full_name} cho JS auto-fill tên khi nhập mã NV.
    profiles = list(UserProfile.objects.exclude(employee_code=''))
    user_map = {p.employee_code: p.full_name for p in profiles if p.employee_code}

    # Dict {email_local_lowercase: employee_code} — cho phép nhập "user"
    # (vd `thanghv37` -> tra ra emp_code `483094`). Chỉ thêm những local part
    # XUẤT HIỆN DUY NHẤT để tránh nhập nhằng (vd 2 user khác đơn vị nhưng cùng
    # local part khác domain). Trùng -> không add vào alias_map -> user buộc
    # phải nhập mã NV.
    from collections import Counter
    locals_count = Counter()
    for p in profiles:
        if p.email and '@' in p.email:
            local = p.email.split('@')[0].strip().lower()
            if local:
                locals_count[local] += 1
    user_alias_map = {}
    for p in profiles:
        if not p.employee_code or not p.email or '@' not in p.email:
            continue
        local = p.email.split('@')[0].strip().lower()
        if local and locals_count[local] == 1:
            user_alias_map[local] = p.employee_code

    if request.method == 'POST':
        date_raw = (request.POST.get('date') or '').strip()
        meal_name = (request.POST.get('meal_name') or '').strip()
        kitchen_name = (request.POST.get('kitchen_name') or '').strip()
        codes = request.POST.getlist('employee_code')
        quantities = request.POST.getlist('quantity')
        # Khách ngoài (không thuộc TTKTKV2) — chỉ cần tên + số suất + ghi chú
        guest_names = request.POST.getlist('guest_name')
        guest_qtys = request.POST.getlist('guest_qty')
        guest_notes = request.POST.getlist('guest_note')

        form_errors = []  # lỗi của field dùng chung

        # --- Validate field dùng chung ---
        parsed_date = None
        if not date_raw:
            form_errors.append('Vui lòng chọn ngày đặt cơm.')
        else:
            try:
                parsed_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
            except ValueError:
                form_errors.append('Ngày đặt cơm không hợp lệ.')

        if not meal_name:
            form_errors.append('Vui lòng chọn bữa ăn.')
        elif meal_name not in meal_options:
            form_errors.append('Bữa ăn không hợp lệ.')

        if not kitchen_name:
            form_errors.append('Vui lòng chọn bếp ăn.')
        elif kitchen_name not in kitchen_options:
            form_errors.append('Bếp ăn không hợp lệ.')

        # --- Dựng từng dòng + validate (dòng không nhập mã → bỏ qua) ---
        rows = []
        seen_codes = set()  # set theo CANONICAL emp_code (sau khi resolve user→emp_code)
        for i, raw_code in enumerate(codes):
            raw = (raw_code or '').strip()
            if not raw:
                continue

            # Resolve raw -> canonical employee_code (chấp nhận emp_code thuần
            # hoặc "user" = local part của email).
            if raw in user_map:
                canonical = raw
            else:
                local = raw.split('@')[0].strip().lower()
                canonical = user_alias_map.get(local, '')

            qty_raw = (quantities[i] if i < len(quantities) else '').strip()
            try:
                qty_int = int(qty_raw) if qty_raw else 1
            except ValueError:
                qty_int = 0

            row = {
                'code': raw,            # giữ raw để hiển thị lại khi lỗi
                'canonical': canonical,
                'name': user_map.get(canonical, ''),
                'quantity': qty_raw or '1',
                'qty_int': qty_int,
                'error': '',
            }

            if qty_int < 1:
                row['error'] = 'Số suất phải là số nguyên ≥ 1.'
            elif not canonical:
                row['error'] = 'Không tìm thấy nhân viên với mã/user này.'
            elif canonical in seen_codes:
                row['error'] = 'Bị trùng trong danh sách (theo mã NV chuẩn).'
            else:
                seen_codes.add(canonical)

            rows.append(row)

        # --- Trùng với đăng kí đã có trong DB (chỉ check khi field chung OK) ---
        if (parsed_date and meal_name in meal_options
                and kitchen_name in kitchen_options):
            valid_codes = [r['canonical'] for r in rows if not r['error']]
            if valid_codes:
                already = set(
                    MealRegistration.objects.filter(
                        date=parsed_date,
                        meal_name=meal_name,
                        kitchen_name=kitchen_name,
                        employee_code__in=valid_codes,
                    ).values_list('employee_code', flat=True)
                )
                for r in rows:
                    if not r['error'] and r['canonical'] in already:
                        r['error'] = ('Người này đã được đăng kí cho '
                                      'ngày / bữa / bếp này.')

        # --- Dựng + validate dòng khách ngoài (không cần tra emp_code) ---
        guest_rows = []
        for i, gname in enumerate(guest_names):
            name = (gname or '').strip()
            qty_raw = (guest_qtys[i] if i < len(guest_qtys) else '').strip()
            note_raw = (guest_notes[i] if i < len(guest_notes) else '').strip()
            # Bỏ qua dòng hoàn toàn trống (cả 3 field rỗng)
            if not name and not qty_raw and not note_raw:
                continue
            try:
                qty_int = int(qty_raw) if qty_raw else 1
            except ValueError:
                qty_int = 0
            gr = {
                'name': name,
                'quantity': qty_raw or '1',
                'qty_int': qty_int,
                'note': note_raw,
                'error': '',
            }
            if not name:
                gr['error'] = 'Vui lòng nhập tên khách.'
            elif qty_int < 1:
                gr['error'] = 'Số suất phải là số nguyên ≥ 1.'
            guest_rows.append(gr)

        if not rows and not guest_rows:
            form_errors.append('Vui lòng nhập ít nhất một người (nhân viên hoặc khách ngoài).')

        has_row_error = any(r['error'] for r in rows) or any(g['error'] for g in guest_rows)

        if form_errors or has_row_error:
            # Có lỗi → không lưu gì, render lại kèm dữ liệu đã nhập.
            display_rows = rows or [
                {'code': '', 'name': '', 'quantity': '1', 'error': ''}
            ]
            return render(request, 'registrations/registration_form.html', {
                'page_title': 'Thêm người đăng kí',
                'meal_options': meal_options,
                'kitchen_options': kitchen_options,
                'user_map': user_map,
                'user_alias_map': user_alias_map,
                'form_errors': form_errors,
                'sel_date': date_raw,
                'sel_meal': meal_name,
                'sel_kitchen': kitchen_name,
                'rows': display_rows,
                'guest_rows': guest_rows,
            })

        # --- Hợp lệ toàn bộ → lưu trong 1 transaction ---
        with transaction.atomic():
            for r in rows:
                MealRegistration.objects.create(
                    employee_code=r['canonical'],
                    full_name=user_map.get(r['canonical'], ''),
                    date=parsed_date,
                    meal_name=meal_name,
                    kitchen_name=kitchen_name,
                    quantity=r['qty_int'],
                    status=STATUS_FIXED,
                    source='manual',
                )
            for g in guest_rows:
                # Sinh emp_code synthetic — UUID hex 12 char, prefix EXT-, đảm
                # bảo unique cho unique_together(emp_code, date, meal, kitchen).
                synthetic_code = f"EXT-{uuid.uuid4().hex[:12]}"
                MealRegistration.objects.create(
                    employee_code=synthetic_code,
                    full_name=g['name'],
                    date=parsed_date,
                    meal_name=meal_name,
                    kitchen_name=kitchen_name,
                    quantity=g['qty_int'],
                    status=STATUS_FIXED,
                    source='guest',
                    note=g['note'],
                )

        total = len(rows) + len(guest_rows)
        guest_note = f' (gồm {len(guest_rows)} khách ngoài)' if guest_rows else ''
        messages.success(request, f'Đã thêm {total} đăng kí suất ăn{guest_note}.')
        return redirect('registration_list')

    # --- GET: form trống với 1 dòng, đề xuất sẵn bữa trưa + bếp khu vực 2 ---
    default_meal, default_kitchen = _default_meal_kitchen(meal_options, kitchen_options)
    return render(request, 'registrations/registration_form.html', {
        'page_title': 'Thêm người đăng kí',
        'meal_options': meal_options,
        'kitchen_options': kitchen_options,
        'user_map': user_map,
        'user_alias_map': user_alias_map,
        'form_errors': [],
        'sel_date': date.today().strftime('%Y-%m-%d'),
        'sel_meal': default_meal,
        'sel_kitchen': default_kitchen,
        'rows': [{'code': '', 'name': '', 'quantity': '1', 'error': ''}],
        'guest_rows': [],  # mặc định section khách ngoài không có dòng nào
    })


@login_required
@user_passes_test(can_manage_menu)
def registration_options(request):
    """Trang cấu hình các option cho dropdown 'Bữa ăn' và 'Tên bếp ăn'."""
    if request.method == 'POST':
        # Frontend submit nhiều input hidden cùng name (1 cho mỗi chip).
        meal_items = request.POST.getlist('meal_options')
        kitchen_items = request.POST.getlist('kitchen_options')
        set_meal_options(meal_items)
        set_kitchen_options(kitchen_items)
        messages.success(request, 'Đã lưu danh sách lựa chọn.')
        return redirect('registration_create')

    return render(request, 'registrations/registration_options.html', {
        'meal_options': get_meal_options(),
        'kitchen_options': get_kitchen_options(),
    })
@login_required
@user_passes_test(can_manage_menu)
@require_POST
def registration_delete(request, pk):
    item = get_object_or_404(MealRegistration, pk=pk)

    redirect_url = request.POST.get('next') or 'registration_list'
    item.delete()

    messages.success(request, 'Đã xóa đăng kí suất ăn.')
    return redirect(redirect_url)

@require_GET
def registrations_by_date_api(request):
    date_str = request.GET.get('date')

    if not date_str:
        return JsonResponse({
            'success': False,
            'message': 'Thiếu tham số date. Ví dụ: ?date=2026-05-04'
        }, status=400)

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Sai định dạng date. Dùng YYYY-MM-DD.'
        }, status=400)

    registrations = MealRegistration.objects.filter(
        date=target_date
    ).exclude(
        employee_code__isnull=True
    ).exclude(
        employee_code=''
    )

    dict_registered_today = {}

    for reg in registrations:
        employee_code = str(reg.employee_code).strip()

        if not employee_code:
            continue

        dict_registered_today[employee_code] = reg.full_name or ''

    return JsonResponse({
        'date': target_date.isoformat(),
        'total_employees_registered': len(dict_registered_today),
        'dict_registered_today': dict_registered_today,
    }, json_dumps_params={
        'ensure_ascii': False
    })
@login_required
def delete_all_registrations(request):

    if not is_admin(request.user):
        return HttpResponseForbidden("Bạn không có quyền xóa dữ liệu.")

    if request.method == 'POST':
        deleted_count, _ = MealRegistration.objects.all().delete()

        messages.success(
            request,
            f'Đã xóa toàn bộ {deleted_count} đăng ký.'
        )

    return redirect('registration_list')


# Nguồn dữ liệu cho MealRegistration tạo từ nút "Đăng ký bổ sung" ở trang Tham gia
# (người quên đăng ký, lên điểm danh rồi xin ăn + nộp tiền bổ sung).
SUPPLEMENTARY_SOURCE = 'supplementary'

_PARTICIPATION_STATUS_LABELS = {
    'valid': ('Đã điểm danh', 'success'),
    'not_registered': ('Chưa đăng ký', 'warning'),
    'not_attended': ('Chưa điểm danh', 'danger'),
    'supplementary': ('Đã đăng ký bổ sung', 'info'),
    # Người không có UserProfile (đơn vị khác thuộc tổng công ty) — không có
    # dữ liệu khuôn mặt nên không điểm danh được, được bypass vào ăn.
    'no_profile': ('Chưa có hồ sơ', 'warning'),
    # Khách ngoài (không thuộc TTKTKV2) — nhập tay với note đơn vị/đối tác,
    # emp_code synthetic EXT-..., không qua nhận diện khuôn mặt.
    'guest': ('Khách ngoài', 'primary'),
}


def _build_participation_rows(target_date):
    """Tạo list rows cho trang Tham gia + export Excel. Dùng chung 2 view."""
    logs = list(AttendanceLog.objects.filter(scan_time__date=target_date).order_by('scan_time'))
    scanned_codes = {(log.employee_code or '').strip() for log in logs}

    # Tách khách ngoài (source='guest') — không có profile, không scan, status='guest'
    all_regs = MealRegistration.objects.filter(date=target_date)
    guest_regs = [r for r in all_regs if r.source == 'guest']
    registrations = [r for r in all_regs if r.source != 'guest']

    registered_name_map = {}
    # 1 người có thể đăng ký nhiều suất (đặt giúp người khác) — cộng dồn quantity.
    registered_quantity_map = {}
    for r in registrations:
        code = (r.employee_code or '').strip()
        if not code:
            continue
        if code not in registered_name_map:
            registered_name_map[code] = (r.full_name or '').strip()
        registered_quantity_map[code] = registered_quantity_map.get(code, 0) + (r.quantity or 0)

    all_codes = scanned_codes | set(registered_name_map.keys())
    profile_map = {
        (p.employee_code or '').strip(): p
        for p in UserProfile.objects.filter(employee_code__in=all_codes)
    }

    # Ảnh chụp lúc quét mặt — mỗi người lấy ảnh mới nhất trong ngày.
    capture_map = {}
    for cap in AttendanceCapture.objects.filter(
            scan_time__date=target_date).order_by('-scan_time'):
        code = (cap.employee_code or '').strip()
        if code and code not in capture_map and cap.image:
            capture_map[code] = cap.image.url

    def _resolve_name(emp_code, profile, fallback_name):
        profile_name = (profile.full_name.strip() if profile and profile.full_name else '')
        if profile_name:
            return profile_name
        if fallback_name and fallback_name != emp_code:
            return fallback_name
        return 'Chưa rõ tên'

    # AttendanceLog.status có thể là english ('not_registered') hoặc tiếng Việt
    # ('Chưa đăng ký') tùy nguồn data — chấp nhận cả 2 dạng.
    NOT_REGISTERED_VALUES = {'not_registered', 'Chưa đăng ký'}

    rows = []
    for log in logs:
        emp_code = (log.employee_code or '').strip()
        profile = profile_map.get(emp_code)
        display_name = _resolve_name(emp_code, profile, (log.full_name or '').strip())
        status_code = log.status
        # Người quét thẻ nhưng AttendanceLog báo "chưa đăng ký" — nếu DB Django
        # đã có MealRegistration (bất kể source: supplementary hay excel/regular)
        # thì coi như đã đăng ký, đổi sang 'supplementary'. Tránh trường hợp
        # AttendanceLog và DB không khớp (vd Excel import xong nhưng external
        # system check theo tiêu chí khác) → user bấm + lặp đi lặp lại.
        if status_code in NOT_REGISTERED_VALUES and emp_code in registered_name_map:
            status_code = 'supplementary'
        # Người không có hồ sơ NV (đơn vị khác) — override trạng thái để giải
        # thích lý do thay vì hiển thị mặc định (vd "chưa điểm danh" sẽ gây hiểu nhầm).
        if not profile:
            status_code = 'no_profile'
        label, css = _PARTICIPATION_STATUS_LABELS.get(status_code, (status_code, 'warning'))
        rows.append({
            'employee_code': emp_code,
            'display_name': display_name,
            'profile': profile,
            'scan_time': log.scan_time,
            'status': status_code,
            'status_label': label,
            'status_class': css,
            'type': log.type or 'Quét thẻ',
            'capture_image_url': capture_map.get(emp_code),
            'quantity': registered_quantity_map.get(emp_code, 0),
            'note': '',
        })

    not_attended_codes = set(registered_name_map.keys()) - scanned_codes
    for emp_code in sorted(not_attended_codes):
        profile = profile_map.get(emp_code)
        display_name = _resolve_name(emp_code, profile, registered_name_map.get(emp_code, ''))
        # Người chưa có hồ sơ — bypass nhận diện, không tính là "chưa điểm danh".
        status_code = 'no_profile' if not profile else 'not_attended'
        label, css = _PARTICIPATION_STATUS_LABELS[status_code]
        rows.append({
            'employee_code': emp_code,
            'display_name': display_name,
            'profile': profile,
            'scan_time': None,
            'status': status_code,
            'status_label': label,
            'status_class': css,
            'type': '—',
            'capture_image_url': None,
            'quantity': registered_quantity_map.get(emp_code, 0),
            'note': '',
        })

    # Khách ngoài — không qua scan/profile, hiển thị riêng dưới status='guest'
    guest_label, guest_css = _PARTICIPATION_STATUS_LABELS['guest']
    for r in guest_regs:
        rows.append({
            'employee_code': (r.employee_code or '').strip(),
            'display_name': (r.full_name or '').strip() or 'Khách ngoài',
            'profile': None,
            'scan_time': None,
            'status': 'guest',
            'status_label': guest_label,
            'status_class': guest_css,
            'type': 'Khách ngoài',
            'capture_image_url': None,
            'quantity': r.quantity or 0,
            'note': (r.note or '').strip(),
        })

    return rows


@login_required
@user_passes_test(can_manage_menu)
@require_POST
def participation_add_supplementary(request):
    """Đăng ký bổ sung: tạo 1 suất ăn cho người đã quét thẻ nhưng chưa đăng ký.

    Lưu dưới dạng MealRegistration source='supplementary' → tự được tính vào
    số suất / doanh thu (Thu) như đăng ký thường.

    Nếu người đó đã có MealRegistration nào ở ngày này (bất kể source) thì
    coi như đã đăng ký rồi → no-op success. Tránh vi phạm unique_together
    `(employee_code, date, meal_name, kitchen_name)` (bug: trên trang Tham gia
    AttendanceLog báo "Chưa đăng ký" nhưng DB lại có record từ Excel import).
    """
    employee_code = (request.POST.get('employee_code') or '').strip()
    date_str = (request.POST.get('date') or '').strip()
    if not employee_code or not date_str:
        return JsonResponse({'success': False, 'message': 'Thiếu dữ liệu.'}, status=400)
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Ngày không hợp lệ.'}, status=400)

    # Đã có bất kỳ bản ghi nào → no-op (tránh tính trùng suất ăn).
    if MealRegistration.objects.filter(
        employee_code=employee_code, date=target_date
    ).exists():
        return JsonResponse({'success': True, 'already_registered': True})

    profile = UserProfile.objects.filter(employee_code=employee_code).first()
    full_name = (profile.full_name if profile and profile.full_name else '') or ''
    default_meal, default_kitchen = _default_meal_kitchen(
        get_meal_options(), get_kitchen_options()
    )

    MealRegistration.objects.create(
        employee_code=employee_code,
        date=target_date,
        source=SUPPLEMENTARY_SOURCE,
        meal_name=default_meal,
        kitchen_name=default_kitchen,
        full_name=full_name,
        quantity=1,
        status='Đặt thành công',
    )
    return JsonResponse({'success': True})


@login_required
@user_passes_test(can_manage_menu)
@require_POST
def participation_remove_supplementary(request):
    """Hủy đăng ký bổ sung (lỡ bấm nhầm) — xóa bản ghi supplementary."""
    employee_code = (request.POST.get('employee_code') or '').strip()
    date_str = (request.POST.get('date') or '').strip()
    if not employee_code or not date_str:
        return JsonResponse({'success': False, 'message': 'Thiếu dữ liệu.'}, status=400)
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Ngày không hợp lệ.'}, status=400)

    MealRegistration.objects.filter(
        employee_code=employee_code,
        date=target_date,
        source=SUPPLEMENTARY_SOURCE,
    ).delete()
    return JsonResponse({'success': True})


@login_required
@user_passes_test(can_manage_menu)
def registration_participation(request):
    # Lấy ngày từ query param hoặc mặc định là hôm nay
    date_str = request.GET.get('date')
    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    q_name = request.GET.get('q_name', '').strip()
    q_status = request.GET.get('q_status', '').strip()

    rows = _build_participation_rows(target_date)

    # Filter UI
    if q_status:
        rows = [r for r in rows if r['status'] == q_status]
    if q_name:
        needle = q_name.lower()
        rows = [r for r in rows if needle in r['display_name'].lower() or needle in r['employee_code'].lower()]

    total_users = len({r['employee_code'] for r in rows})

    # user_map cho modal cấu hình NetChat — JS auto-fill họ tên khi nhập MNV.
    user_map = {
        p.employee_code: p.full_name
        for p in UserProfile.objects.exclude(employee_code='')
        if p.employee_code
    }

    context = {
        'rows': rows,
        'target_date': target_date,
        'q_name': q_name,
        'q_status': q_status,
        'total_users': total_users,
        'user_map': user_map,
        'can_delete_scan': is_admin(request.user),  # chỉ admin thấy nút xóa lượt quét
    }
    return render(request, 'registrations/registration_participation.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def participation_delete_scan(request):
    """Xóa lượt quét (AttendanceLog) + ảnh chụp của 1 người trong 1 ngày.

    Chỉ admin. MealRegistration được GIỮ NGUYÊN — sau khi xóa, nếu người đó
    có đăng ký thì chuyển thành 'chưa điểm danh', nếu không thì biến mất khỏi
    danh sách Tham gia.
    """
    employee_code = (request.POST.get('employee_code') or '').strip()
    date_str = (request.POST.get('date') or '').strip()
    if not employee_code or not date_str:
        return JsonResponse({'success': False, 'message': 'Thiếu dữ liệu.'}, status=400)
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Ngày không hợp lệ.'}, status=400)

    logs_deleted, _ = AttendanceLog.objects.filter(
        employee_code=employee_code,
        scan_time__date=target_date,
    ).delete()

    # Xóa kèm ảnh chụp (xóa file ảnh: lặp .delete() từng cái để gọi storage).
    captures = AttendanceCapture.objects.filter(
        employee_code=employee_code,
        scan_time__date=target_date,
    )
    caps_deleted = 0
    for cap in captures:
        if cap.image:
            cap.image.delete(save=False)
        cap.delete()
        caps_deleted += 1

    if not logs_deleted and not caps_deleted:
        return JsonResponse({
            'success': False,
            'message': 'Không tìm thấy lượt quét nào để xóa.',
        }, status=404)

    return JsonResponse({
        'success': True,
        'message': f'Đã xóa {logs_deleted} lượt quét, {caps_deleted} ảnh.',
    })


def _parse_date_param(request):
    date_str = request.GET.get('date') or request.POST.get('date')
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
    return date.today()


@login_required
@user_passes_test(can_manage_menu)
def export_participation_excel(request):
    """Tải Excel danh sách tham gia 1 ngày (3 trạng thái)."""
    from django.http import HttpResponse
    from .participation_export import build_excel_bytes

    target_date = _parse_date_param(request)
    rows = _build_participation_rows(target_date)
    file_bytes = build_excel_bytes(target_date, rows)

    filename = f'tham_gia_{target_date.strftime("%Y-%m-%d")}.xlsx'
    response = HttpResponse(
        file_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@user_passes_test(can_manage_menu)
@require_POST
def participation_send_netchat(request):
    """Gửi Excel báo cáo qua NetChat — DM tới từng người hoặc đăng vào channel,
    tùy hình thức đã chọn trong Cài đặt."""
    from .participation_export import build_excel_bytes, send_participation_excel

    target_date = _parse_date_param(request)
    rows = _build_participation_rows(target_date)
    file_bytes = build_excel_bytes(target_date, rows)
    result = send_participation_excel(target_date, file_bytes, rows)

    return JsonResponse({
        'success': result['ok'],
        'message': result['message'],
    })


@login_required
def participation_counts_api(request):
    """Số liệu tham gia realtime cho ô KPI 'Người ăn' trên dashboard."""
    from .participation_export import count_statuses

    target_date = _parse_date_param(request)
    rows = _build_participation_rows(target_date)
    counts = count_statuses(rows)
    return JsonResponse({'success': True, **counts})


@login_required
@user_passes_test(can_manage_menu)
def participation_settings(request):
    """GET: trả về settings hiện tại. POST: lưu settings."""
    from .participation_export import (
        get_recipients,
        set_recipients,
        get_send_time,
        set_send_time,
        get_send_mode,
        set_send_mode,
        get_channel_id,
        set_channel_id,
        get_send_days,
        set_send_days,
    )

    if request.method == 'POST':
        send_time_raw = (request.POST.get('send_time') or '').strip()
        recipients_raw = request.POST.get('recipients', '')
        mode_raw = (request.POST.get('mode') or '').strip()
        channel_id_raw = (request.POST.get('channel_id') or '').strip()
        send_days_raw = request.POST.get('send_days', '')
        codes = [line.strip() for line in recipients_raw.splitlines() if line.strip()]
        try:
            saved_time = set_send_time(send_time_raw)
        except ValueError as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        saved_mode = set_send_mode(mode_raw)
        saved_codes = set_recipients(codes)
        saved_channel = set_channel_id(channel_id_raw)
        saved_days = set_send_days(send_days_raw)
        existing = set(UserProfile.objects.filter(employee_code__in=saved_codes).values_list('employee_code', flat=True))
        invalid = [c for c in saved_codes if c not in existing]
        return JsonResponse({
            'success': True,
            'send_time': saved_time,
            'mode': saved_mode,
            'recipients': saved_codes,
            'channel_id': saved_channel,
            'send_days': saved_days,
            'invalid_codes': invalid,
        })

    return JsonResponse({
        'success': True,
        'send_time': get_send_time(),
        'mode': get_send_mode(),
        'recipients': get_recipients(),
        'channel_id': get_channel_id(),
        'send_days': get_send_days(),
    })


# --- HÀM CHẠY NGẦM GỬI TIN NHẮN (BACKGROUND THREAD) ---
# Số lượt thử tối đa cho mỗi người (bao gồm lượt đầu). Sau lượt đầu, gom lại
# những người gặp lỗi tạm thời (mạng / 5xx / 429 / timeout) rồi thử lại — lỗi
# vĩnh viễn (không có account NetChat, 401/403) bỏ qua luôn.
MAX_NOTIFICATION_PASSES = 3
# Nghỉ giữa các lượt retry để rate limit / network kịp hồi.
RETRY_PASS_SLEEP_SECONDS = 30


_DISH_TYPE_EMOJI = {
    'main': '🍚',
    'side': '🥬',
    'soup': '🍲',
    'dessert': '🍮',
}
_DISH_TYPE_ORDER = {'main': 1, 'side': 2, 'soup': 3, 'dessert': 4}


def _build_menu_summary(target_date):
    """Dựng đoạn text liệt kê món ăn của ngày target_date — mỗi dòng 1 món
    với emoji theo loại, sort main → side → soup → dessert.
    Trả '' nếu chưa có menu cho ngày đó."""
    from meals.models import DailyMenu
    menu = (DailyMenu.objects
            .filter(date=target_date)
            .prefetch_related('items__dish')
            .order_by('-created_at')
            .first())
    if not menu:
        return '_(Chưa có thực đơn cho ngày này)_'
    items = sorted(
        menu.items.all(),
        key=lambda it: (
            _DISH_TYPE_ORDER.get(it.dish.dish_type, 99),
            it.sort_order,
            (it.dish.name or '').lower(),
        ),
    )
    lines = []
    for it in items:
        emoji = _DISH_TYPE_EMOJI.get(it.dish.dish_type, '🍽️')
        lines.append(f"{emoji} {it.dish.name}")
    return '\n'.join(lines)


def _build_review_link():
    """URL công khai trang đánh giá món ăn, dạng absolute để click trong NetChat."""
    from django.conf import settings
    from django.urls import reverse
    base = (settings.SITE_URL or '').rstrip('/')
    try:
        path = reverse('public_review')
    except Exception:
        path = '/reviews/public/'
    return f"{base}{path}"


def _send_one_notification(emp_code, username, full_name, reg,
                           netchat_url, headers, bot_id, formatted_date,
                           menu_summary='', review_link=''):
    """Gửi tin cho 1 người.

    Trả về tuple ``(result, error)`` với ``result`` ∈ {'success', 'permanent',
    'retryable'}. ``permanent`` = không nên retry (account không tồn tại,
    401/403). ``retryable`` = nên thử lại lượt sau (timeout, 5xx, 429, mạng).

    ``menu_summary`` và ``review_link`` chung cho cả lô (cùng ngày), được
    compute 1 lần ở ``_send_notifications_bg`` rồi truyền xuống.
    """
    try:
        # Bước A: Tìm Mattermost ID theo Username
        r_user = requests.get(
            f"{netchat_url}/api/v4/users/username/{username}",
            headers=headers, timeout=10,
        )
        if r_user.status_code == 404:
            return ('permanent', 'Không tìm thấy tài khoản trên NetChat')
        if r_user.status_code in (401, 403):
            return ('permanent', f'Lỗi xác thực khi tra cứu user (HTTP {r_user.status_code})')
        if r_user.status_code != 200:
            return ('retryable', f'Tra cứu user lỗi HTTP {r_user.status_code}: {r_user.text[:200]}')
        mm_user_id = r_user.json().get('id')
        if not mm_user_id:
            return ('permanent', 'Phản hồi NetChat thiếu user id')

        # Bước B: Mở Direct Message (DM)
        r_channel = requests.post(
            f"{netchat_url}/api/v4/channels/direct",
            headers=headers, json=[bot_id, mm_user_id], timeout=10,
        )
        if r_channel.status_code in (401, 403):
            return ('permanent', f'Lỗi xác thực khi mở DM (HTTP {r_channel.status_code})')
        if r_channel.status_code not in (200, 201):
            return ('retryable', f'Lỗi mở kênh chat HTTP {r_channel.status_code}: {r_channel.text[:200]}')
        channel_id = r_channel.json().get('id')
        if not channel_id:
            return ('retryable', 'Phản hồi mở kênh thiếu channel id')

        # Bước C: Gửi tin nhắn (template lấy từ SystemConfig)
        from core.message_templates import get_meal_template, render_template
        message = render_template(
            get_meal_template(),
            full_name=full_name,
            employee_code=emp_code,
            meal_name=reg.meal_name,
            meal_count=f"{reg.quantity:02d}",
            target_date=formatted_date,
            kitchen_name=reg.kitchen_name,
            menu_summary=menu_summary,
            review_link=review_link,
        )
        r_post = requests.post(
            f"{netchat_url}/api/v4/posts",
            headers=headers, json={"channel_id": channel_id, "message": message}, timeout=10,
        )
        if r_post.status_code in (200, 201):
            return ('success', None)
        if r_post.status_code in (401, 403):
            return ('permanent', f'Lỗi xác thực khi gửi tin (HTTP {r_post.status_code})')
        return ('retryable', f'Lỗi gửi tin HTTP {r_post.status_code}: {r_post.text[:200]}')

    except requests.exceptions.RequestException as e:
        return ('retryable', f'Lỗi mạng: {str(e)[:200]}')
    except Exception as e:
        return ('retryable', f'Lỗi không xác định: {str(e)[:200]}')


def _send_notifications_bg(employee_codes, target_date, config):
    netchat_url = config.get('netchat_url', '').strip().rstrip('/')
    netchat_token = config.get('netchat_token', '').strip()

    if not netchat_url or not netchat_token:
        print("[NetChat] Lỗi: Chưa cấu hình Bot URL hoặc Token.")
        return

    headers = {
        "Authorization": f"Bearer {netchat_token}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.7.1"  # <--- THÊM DÒNG NÀY ĐỂ VƯỢT TƯỜNG LỬA CLOUDRITY
    }
    # 1. Lấy ID của Bot
    try:
        r_me = requests.get(f"{netchat_url}/api/v4/users/me", headers=headers, timeout=10)
        if r_me.status_code != 200:
            print("[NetChat] Lỗi lấy Bot ID:", r_me.text)
            return
        bot_id = r_me.json().get('id')
    except Exception as e:
        print("[NetChat] Lỗi kết nối:", str(e))
        return

    # Lấy thông tin user (để lấy email -> username) và thông tin bữa ăn
    profiles = UserProfile.objects.filter(employee_code__in=employee_codes)
    profile_dict = {p.employee_code: p for p in profiles}

    registrations = MealRegistration.objects.filter(date=target_date, employee_code__in=employee_codes)
    reg_dict = {r.employee_code: r for r in registrations}

    # Format ngày sang DD-MM-YYYY cho user-friendly trong tin nhắn (target_date
    # đến từ frontend dạng ISO 'YYYY-MM-DD' của <input type="date">).
    try:
        formatted_date = datetime.strptime(str(target_date), '%Y-%m-%d').strftime('%d-%m-%Y')
    except (ValueError, TypeError):
        formatted_date = str(target_date)

    # Build menu_summary + review_link 1 lần (chung cho cả lô — cùng ngày).
    menu_summary = _build_menu_summary(target_date)
    review_link = _build_review_link()

    # State xuyên suốt các lượt — chỉ tạo NotificationLog 1 lần cho mỗi người
    # ở cuối, sau khi đã định đoạt: success / permanent / retry exhausted.
    pending = list(employee_codes)        # MNV cần thử ở lượt kế tiếp
    success_set = set()                   # MNV đã gửi thành công
    permanent_failed = {}                 # MNV -> lỗi vĩnh viễn (đã bỏ)
    last_error = {}                       # MNV -> lỗi gần nhất (dùng cho retry exhausted)
    full_name_map = {}                    # MNV -> tên (để ghi log)
    attempt_counter = 0                   # tổng số tin đã gửi (throttle 60s/15 tin)

    for pass_num in range(1, MAX_NOTIFICATION_PASSES + 1):
        if not pending:
            break
        if pass_num > 1:
            print(f"[NetChat] Bắt đầu lượt retry #{pass_num - 1} cho {len(pending)} người. "
                  f"Tạm nghỉ {RETRY_PASS_SLEEP_SECONDS}s...")
            time.sleep(RETRY_PASS_SLEEP_SECONDS)
        else:
            print(f"[NetChat] Lượt 1: gửi cho {len(pending)} người.")

        next_pending = []
        for emp_code in pending:
            profile = profile_dict.get(emp_code)
            reg = reg_dict.get(emp_code)

            if not profile or not profile.email or not reg:
                # Lỗi vĩnh viễn ở phía dữ liệu nội bộ — giữ behavior cũ: print + không log.
                print(f"[NetChat] Bỏ qua {emp_code}: Thiếu profile, email hoặc chưa đăng ký bữa ăn.")
                permanent_failed[emp_code] = None  # None = bỏ qua không log
                if profile:
                    full_name_map[emp_code] = profile.full_name
                elif reg:
                    full_name_map[emp_code] = reg.full_name
                continue

            # Throttle: cứ 15 tin thật sự gửi đi thì nghỉ 60s
            if attempt_counter > 0 and attempt_counter % 15 == 0:
                print(f"[NetChat] Đã gửi {attempt_counter} tin. Tạm nghỉ 60s để tránh spam...")
                time.sleep(60)
            attempt_counter += 1

            username = profile.email.split('@')[0].strip().lower()
            full_name = profile.full_name or reg.full_name
            full_name_map[emp_code] = full_name

            result, err = _send_one_notification(
                emp_code, username, full_name, reg,
                netchat_url, headers, bot_id, formatted_date,
                menu_summary=menu_summary, review_link=review_link,
            )

            if result == 'success':
                success_set.add(emp_code)
            elif result == 'permanent':
                print(f"[NetChat] Bỏ {username}: {err}")
                permanent_failed[emp_code] = err
                last_error[emp_code] = err
            else:
                # retryable — để lượt sau thử lại
                print(f"[NetChat] Tạm bỏ qua {username} (sẽ retry): {err}")
                last_error[emp_code] = err
                next_pending.append(emp_code)

        pending = next_pending

    # Ghi NotificationLog 1 lần cho mỗi MNV theo kết quả cuối cùng
    for emp_code in employee_codes:
        full_name = full_name_map.get(emp_code, '')
        if emp_code in success_set:
            NotificationLog.objects.create(
                target_date=target_date, employee_code=emp_code,
                full_name=full_name, status='success',
            )
        elif emp_code in permanent_failed:
            err = permanent_failed[emp_code]
            if err is None:
                # Bỏ qua không log (thiếu profile/email/reg) — giữ behavior cũ
                continue
            NotificationLog.objects.create(
                target_date=target_date, employee_code=emp_code,
                full_name=full_name, status='failed',
                error_message=err[:500],
            )
        else:
            # Retry exhausted — vẫn còn trong pending hoặc có last_error nhưng chưa success
            err = last_error.get(emp_code, 'Không rõ lỗi')
            NotificationLog.objects.create(
                target_date=target_date, employee_code=emp_code,
                full_name=full_name, status='failed',
                error_message=f'[Đã thử {MAX_NOTIFICATION_PASSES} lượt] {err}'[:500],
            )

    print(f"[NetChat] Hoàn tất tiến trình. Thành công: {len(success_set)}/{len(employee_codes)} "
          f"(còn {len(pending)} người fail sau {MAX_NOTIFICATION_PASSES} lượt).")
    # Clear state job-active để UI biết có thể bấm lại.
    SystemConfig.objects.filter(key='notification_job_active_until').update(value='')


@login_required
@user_passes_test(can_manage_menu) # Phân quyền
@require_POST
def send_meal_notifications(request):
    try:
        data = json.loads(request.body)
        employee_codes = data.get('employee_codes', [])
        date_str = data.get('date', '')

        if not employee_codes or not date_str:
            return JsonResponse({'success': False, 'message': 'Dữ liệu không hợp lệ.'}, status=400)

        # ---- ĐOẠN CODE MỚI LẤY CẤU HÌNH TỪ DATABASE ----
        from core.models import SystemConfig  # Đảm bảo import đúng đường dẫn model SystemConfig của bạn

        try:
            # Tìm trong database cấu hình đã lưu
            url_obj = SystemConfig.objects.get(key='netchat_url')
            token_obj = SystemConfig.objects.get(key='netchat_token')
            
            config = {
                'netchat_url': url_obj.value.strip(),
                'netchat_token': token_obj.value.strip(),
            }
        except SystemConfig.DoesNotExist:
            # Nếu chưa có ai nhập cấu hình trong tab Profile
            return JsonResponse({
                'success': False, 
                'message': 'Chưa cấu hình URL hoặc Token BOT. Vui lòng vào Hồ sơ cá nhân để thiết lập.'
            }, status=400)
        # ------------------------------------------------

        # Ghi state job-active trước khi start thread → UI restore countdown sau reload.
        # Estimate: ceil(N/15) * 75 + 15 (khớp với JS frontend).
        import math
        n = len(employee_codes)
        estimated_sec = max(15, math.ceil(n / 15) * 75 + 15)
        active_until = (now() + timedelta(seconds=estimated_sec)).isoformat()
        SystemConfig.objects.update_or_create(
            key='notification_job_active_until',
            defaults={'value': active_until},
        )
        SystemConfig.objects.update_or_create(
            key='notification_job_total',
            defaults={'value': str(n)},
        )

        # Tạo thread chạy ngầm để không làm treo trình duyệt
        thread = threading.Thread(
            target=_send_notifications_bg,
            args=(employee_codes, date_str, config)
        )
        thread.daemon = True # Thread sẽ tự tắt nếu server tắt
        thread.start()

        return JsonResponse({'success': True, 'message': 'Đã nhận lệnh gửi.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@require_GET
def get_notification_logs_api(request):
    date_str = request.GET.get('date')
    if not date_str:
        date_str = date.today().isoformat()
    
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Sai định dạng ngày'})

    logs = NotificationLog.objects.filter(target_date=target_date).order_by('-created_at')

    # Lấy log mới nhất của mỗi người dùng trong ngày đó (nếu gửi nhiều lần, chỉ lấy lần cuối)
    # Vì SQLite không hỗ trợ DISTINCT ON, ta xử lý bằng code Python
    latest_logs = {}
    for log in logs:
        if log.employee_code not in latest_logs:
            latest_logs[log.employee_code] = log

    final_logs = list(latest_logs.values())

    success_count = sum(1 for log in final_logs if log.status == 'success')
    failed_count = sum(1 for log in final_logs if log.status == 'failed')

    log_data = []
    for log in final_logs:
        log_data.append({
            'employee_code': log.employee_code,
            'full_name': log.full_name,
            'status': log.status,
            'error_message': log.error_message,
            'time': log.created_at.strftime('%H:%M')
        })

    # Danh sách "chưa gửi" = người có trong đăng ký ngày này nhưng chưa có log nào.
    # Lấy full_name từ MealRegistration; dedup theo employee_code.
    registered_rows = MealRegistration.objects.filter(
        date=target_date
    ).values('employee_code', 'full_name')

    registered_names = {}
    for r in registered_rows:
        code = r['employee_code']
        if code and code not in registered_names:
            registered_names[code] = r['full_name'] or ''

    pending_data = [
        {'employee_code': code, 'full_name': name}
        for code, name in registered_names.items()
        if code not in latest_logs
    ]
    pending_data.sort(key=lambda x: x['employee_code'])
    pending_count = len(pending_data)

    return JsonResponse({
        'success': True,
        'success_count': success_count,
        'failed_count': failed_count,
        'pending_count': pending_count,
        'logs': log_data,
        'pending': pending_data,
    })


# ============================================================================
# MODULE CHUYỂN SUẤT ĂN (Meal Transfer) — đặt trong trang Profile.
# Logic trong registrations/meal_transfer.py. Views ở đây chỉ xử lý request.
# ============================================================================

from .models import MealTransfer  # noqa: E402  (đặt cuối file để tránh circular)


@login_required
@require_GET
def meal_transfer_lookup(request):
    """AJAX tra cứu user nhận theo mã NV / username / user (= local part của email).

    Match-by-email-prefix: dùng `__istartswith=f'{local}@'` để khớp chính xác
    `annt830@viettel.com.vn` mà KHÔNG khớp `annt8300@...` (vì sau prefix bắt buộc
    là ký tự `@`). Nếu nhiều profile cùng local part (khác domain) -> báo lỗi,
    yêu cầu dùng mã NV chính xác để tránh nhầm.
    """
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'success': False, 'message': 'Vui lòng nhập mã NV hoặc tên đăng nhập.'})

    # Nếu user paste full email, vẫn lấy được local part.
    local_part = q.split('@')[0].strip()

    qs = UserProfile.objects.filter(
        Q(employee_code__iexact=q)
        | Q(user__username__iexact=q)
        | Q(email__istartswith=f'{local_part}@')
    ).select_related('user').distinct()

    matches = list(qs[:5])
    if not matches:
        return JsonResponse({'success': False, 'message': f'Không tìm thấy nhân viên "{q}".'})
    if len(matches) > 1:
        codes = ', '.join((p.employee_code or '?') for p in matches)
        return JsonResponse({
            'success': False,
            'message': f'Có {len(matches)} người khớp "{q}" ({codes}). Vui lòng nhập mã NV chính xác.',
        })

    profile = matches[0]
    return JsonResponse({
        'success': True,
        'employee_code': profile.employee_code or '',
        'full_name': profile.full_name or '',
        'unit': profile.unit or '',
        'department': profile.department or '',
        'email': profile.email or '',
        'avatar_url': profile.avatar.url if profile.avatar else '',
    })


@login_required
@require_POST
def meal_transfer_create(request):
    """Tạo yêu cầu chuyển suất ăn. Apply ngay nếu A có data, ngược lại pending."""
    from .meal_transfer import (
        apply_meal_transfer, is_within_cutoff, _safe_send_netchat,
    )

    user = request.user
    profile = getattr(user, 'profile', None)
    if not profile or not profile.employee_code:
        return JsonResponse(
            {'success': False, 'message': 'Tài khoản của bạn chưa có mã NV — không thể chuyển suất ăn.'},
            status=400,
        )

    date_str = (request.POST.get('meal_date') or '').strip()
    to_emp = (request.POST.get('to_employee_code') or '').strip()
    note = (request.POST.get('note') or '').strip()

    if not date_str or not to_emp:
        return JsonResponse(
            {'success': False, 'message': 'Thiếu thông tin ngày hoặc người nhận.'},
            status=400,
        )

    try:
        meal_date = date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Ngày không hợp lệ.'}, status=400)

    if not is_within_cutoff(meal_date):
        return JsonResponse(
            {'success': False,
             'message': f'Đã quá 11h ngày {meal_date.strftime("%d/%m/%Y")} — không chuyển được nữa.'},
            status=400,
        )

    if to_emp == profile.employee_code:
        return JsonResponse({'success': False, 'message': 'Không thể chuyển cho chính mình.'}, status=400)

    to_profile = UserProfile.objects.filter(
        Q(employee_code__iexact=to_emp) | Q(user__username__iexact=to_emp)
    ).select_related('user').first()
    if not to_profile:
        return JsonResponse({'success': False, 'message': f'Không tìm thấy người nhận "{to_emp}".'}, status=400)

    # Chặn tạo trùng — đã có pending/applied cho cùng ngày từ A.
    existing = MealTransfer.objects.filter(
        from_employee_code=profile.employee_code,
        meal_date=meal_date,
        status__in=[MealTransfer.STATUS_PENDING, MealTransfer.STATUS_APPLIED],
    ).first()
    if existing:
        return JsonResponse(
            {'success': False,
             'message': f'Bạn đã có yêu cầu chuyển ngày này ({existing.get_status_display()}). '
                        f'Hủy yêu cầu cũ trước khi tạo mới.'},
            status=400,
        )

    transfer = MealTransfer.objects.create(
        from_user=user,
        from_employee_code=profile.employee_code,
        from_full_name=profile.full_name or '',
        to_user=getattr(to_profile, 'user', None),
        to_employee_code=to_profile.employee_code or to_emp,
        to_full_name=to_profile.full_name or '',
        meal_date=meal_date,
        note=note,
    )

    status, keys = apply_meal_transfer(transfer)
    date_str = meal_date.strftime('%d/%m/%Y')

    if status == 'applied':
        _safe_send_netchat(transfer, 'applied', transferred_keys=keys)
        meals_disp = ', '.join(m or '?' for m, _k in keys) or 'suất ăn'
        return JsonResponse({
            'success': True,
            'status': 'applied',
            'message': f'Đã chuyển {meals_disp} ngày {date_str} cho '
                       f'{to_profile.full_name or to_emp}.',
        })

    if status == 'b_already_registered':
        # B đã có đăng ký trùng -> hủy luôn, báo cả 2 bên.
        transfer.status = MealTransfer.STATUS_CANCELLED
        transfer.cancel_reason = f'{to_profile.full_name or to_emp} đã có đăng ký trùng bữa/bếp.'
        transfer.save(update_fields=['status', 'cancel_reason'])
        _safe_send_netchat(transfer, 'failed_b_conflict', conflict_keys=keys)
        meals_disp = ', '.join(m or '?' for m, _k in keys) or 'suất ăn'
        return JsonResponse({
            'success': False,
            'status': 'failed_b_conflict',
            'message': f'Không chuyển được: {to_profile.full_name or to_emp} đã có đăng ký '
                       f'"{meals_disp}" ngày {date_str}. Yêu cầu đã bị hủy.',
        })

    # 'a_not_registered' -> giữ pending, đợi data sync hoặc hết hạn.
    _safe_send_netchat(transfer, 'pending')
    return JsonResponse({
        'success': True,
        'status': 'pending',
        'message': f'Đã ghi nhận yêu cầu. Hệ thống sẽ tự áp dụng khi data đăng ký '
                   f'ngày {date_str} được nhập (trước 11h ngày đó).',
    })


@login_required
@require_POST
def meal_transfer_cancel(request, pk):
    """Hủy yêu cầu pending — chỉ chính người tạo hoặc admin được hủy."""
    transfer = get_object_or_404(MealTransfer, pk=pk)
    is_owner = transfer.from_user_id == request.user.id
    if not (is_owner or is_admin(request.user)):
        return JsonResponse({'success': False, 'message': 'Không có quyền hủy yêu cầu này.'}, status=403)
    if transfer.status != MealTransfer.STATUS_PENDING:
        return JsonResponse(
            {'success': False,
             'message': f'Chỉ hủy được yêu cầu đang chờ (hiện tại: {transfer.get_status_display()}).'},
            status=400,
        )

    transfer.status = MealTransfer.STATUS_CANCELLED
    transfer.cancel_reason = 'Người tạo hủy.' if is_owner else 'Admin hủy.'
    transfer.save(update_fields=['status', 'cancel_reason'])
    return JsonResponse({'success': True, 'message': 'Đã hủy yêu cầu.'})