#core/views
from datetime import date, timedelta
from meals.models import DailyMenu
from registrations.models import MealRegistration
from django.db.models import Count, Q, Sum
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.permissions import can_view_dashboard, can_manage_meal_price
from finance.models import DailyPurchase
from .models import MealPriceSetting, MealPriceChangeLog
from .forms import MealPriceSettingForm
from django.db.models import Count
import calendar
from django.db.models import Q
from django.utils import timezone
from datetime import time
from .models import DailyNutritionAnalysis
from core.services.nutrition_ai import estimate_nutrition
from django.http import JsonResponse
from datetime import time
from django.utils import timezone
from .models import DailyNutritionAnalysis
from .services.nutrition_ai import estimate_nutrition
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import (
    AttendanceLog, RecognitionHeartbeat, CameraStatusLog, SystemConfig,
    AttendanceCapture,
)
from django.utils.dateparse import parse_datetime

def get_registered_count(target_date):
    total = MealRegistration.objects.filter(
        date=target_date
    ).aggregate(total=Sum('quantity'))['total']

    return total or 0


def get_price_setting_for_date(target_date):
    price_setting = MealPriceSetting.objects.filter(
        start_date__lte=target_date
    ).order_by('-start_date').first()

    if not price_setting:
        return None

    if price_setting.end_date is None:
        return price_setting

    if price_setting.start_date <= target_date <= price_setting.end_date:
        return price_setting

    return None


def get_price_breakdown_for_date(target_date):
    """Trả về dict {'meal', 'food', 'spice'} cho ngày, hoặc None nếu chưa set giá."""
    price_setting = get_price_setting_for_date(target_date)

    if not price_setting:
        return None

    meal = int(price_setting.meal_price or 0)
    spice = int(price_setting.spice_price or 0)

    return {
        'meal': meal,
        'spice': spice,
        'food': meal - spice,
    }


def get_meal_price_for_date(target_date):
    """Giá suất ăn tổng cho 1 ngày (giữ tương thích cho module báo cáo)."""
    breakdown = get_price_breakdown_for_date(target_date)

    if breakdown is None:
        return None

    return breakdown['meal']


def staff_required(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(can_view_dashboard)
def dashboard(request):
    selected_date_str = request.GET.get('date')

    if selected_date_str:
        try:
            selected_date = date.fromisoformat(selected_date_str)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    price_breakdown = get_price_breakdown_for_date(selected_date)
    registered_count = get_registered_count(selected_date)

    if price_breakdown:
        meal_price = price_breakdown['meal']
        food_price = price_breakdown['food']
        spice_price = price_breakdown['spice']
    else:
        meal_price = food_price = spice_price = None

    menu = DailyMenu.objects.filter(date=selected_date,status=DailyMenu.STATUS_APPROVED).prefetch_related('items__dish').first()

    ordered_menu_items = []
    grouped_menu_items = {
        'main': [],
        'side': [],
        'soup': [],
        'dessert': [],
    }
    dish_type_order = {
            'main': 1,
            'side': 2,
            'soup': 3,
            'dessert': 4,
        }
    if menu:
        # Cơm luôn ưu tiên đầu trong nhóm "main" — bếp Việt cơm là món nền tảng
        def _rice_priority(item):
            name = (item.dish.name or '').lower().strip()
            # match 'cơm', 'cơm trắng', 'cơm chiên...' nhưng KHÔNG match 'cá cơm'
            return 0 if name.startswith('cơm') else 1

        # 1. sort menu trước
        ordered_menu_items = sorted(
            menu.items.all(),
            key=lambda item: (
                dish_type_order.get(item.dish.dish_type, 99),
                _rice_priority(item),
                item.sort_order,
                item.dish.name.lower(),
            )
        )

        # 2. group menu
        for item in ordered_menu_items:
            grouped_menu_items[item.dish.dish_type].append(item)

    purchases_today = DailyPurchase.objects.filter(
        date=selected_date,
        status=DailyPurchase.STATUS_APPROVED
    ).select_related('created_by').prefetch_related('extra_items')

    # Chi phí trong ngày tách theo phân loại hóa đơn: thực phẩm vs gia vị
    expense_food = int(purchases_today.filter(
        purchase_type=DailyPurchase.PURCHASE_TYPE_MAIN
    ).aggregate(total=Sum('actual_cost'))['total'] or 0)
    expense_spice = int(purchases_today.filter(
        purchase_type=DailyPurchase.PURCHASE_TYPE_EXTRA
    ).aggregate(total=Sum('actual_cost'))['total'] or 0)
    total_expense = expense_food + expense_spice

    if price_breakdown:
        income_food = registered_count * food_price
        income_spice = registered_count * spice_price
        total_income = income_food + income_spice

        balance_food = income_food - expense_food
        balance_spice = income_spice - expense_spice
        balance = total_income - total_expense
    else:
        income_food = income_spice = total_income = None
        balance_food = balance_spice = balance = None

    chart_labels = []
    income_food_data = []
    income_spice_data = []
    expense_food_data = []
    expense_spice_data = []
    balance_food_data = []
    balance_spice_data = []

    # Xác định thứ 2 của tuần chứa selected_date
    start_of_week = selected_date - timedelta(days=selected_date.weekday())

    # Chỉ hiển thị 5 ngày làm việc: thứ 2 -> thứ 6
    week_days = [start_of_week + timedelta(days=i) for i in range(5)]

    # Chi phí cả tuần, tách theo phân loại để vẽ chart
    purchase_food_map = {}
    purchase_spice_map = {}

    for item in DailyPurchase.objects.filter(
        date__range=(week_days[0], week_days[-1]),
        status=DailyPurchase.STATUS_APPROVED
    ).values('date', 'purchase_type').annotate(total_cost=Sum('actual_cost')):
        cost = int(item['total_cost'] or 0)
        if item['purchase_type'] == DailyPurchase.PURCHASE_TYPE_EXTRA:
            purchase_spice_map[item['date']] = purchase_spice_map.get(item['date'], 0) + cost
        else:
            purchase_food_map[item['date']] = purchase_food_map.get(item['date'], 0) + cost

    week_menus_queryset = DailyMenu.objects.filter(
        date__range=(week_days[0], week_days[-1]),status=DailyMenu.STATUS_APPROVED
    ).annotate(item_count=Count('items')).prefetch_related('items__dish')
    week_menu_map = {m.date: m for m in week_menus_queryset}
    weekday_labels = {
        0: 'Thứ 2',
        1: 'Thứ 3',
        2: 'Thứ 4',
        3: 'Thứ 5',
        4: 'Thứ 6',
    }
    profile = getattr(request.user, 'profile', None)

    if profile and profile.employee_code:
        employee_code = profile.employee_code
    else:
        employee_code = request.user.username
    registration_dates = set(
        MealRegistration.objects.filter(
            employee_code=employee_code,
            date__range=(week_days[0], week_days[-1]),
        ).values_list('date', flat=True)
    )
    week_data = []

    for d in week_days:
        day_menu = week_menu_map.get(d)

        sorted_items = sorted(
            day_menu.items.all(),
            key=lambda item: (
                dish_type_order.get(item.dish.dish_type, 99),
                item.sort_order,
                item.dish.name.lower(),
            )
        ) if day_menu else []

        week_groups = [
            {
                'label': 'Món chính',
                'type': 'main',
                'items': [item for item in sorted_items if item.dish.dish_type == 'main'],
            },
            {
                'label': 'Món phụ',
                'type': 'side',
                'items': [item for item in sorted_items if item.dish.dish_type == 'side'],
            },
            {
                'label': 'Món canh',
                'type': 'soup',
                'items': [item for item in sorted_items if item.dish.dish_type == 'soup'],
            },
            {
                'label': 'Tráng miệng',
                'type': 'dessert',
                'items': [item for item in sorted_items if item.dish.dish_type == 'dessert'],
            },
        ]

        week_data.append({
            'date': d,
            'date_str': d.isoformat(),
            'label': weekday_labels.get(d.weekday(), ''),
            'menu': day_menu,
            'menu_items': sorted_items,
            'menu_groups': week_groups,
            'is_registered': d in registration_dates,
        })

    

    week_menu_cards = []
    

    
    for d in week_days:
        count = get_registered_count(d)
        day_price = get_price_breakdown_for_date(d)
        day_menu = week_menu_map.get(d)

        day_expense_food = purchase_food_map.get(d, 0)
        day_expense_spice = purchase_spice_map.get(d, 0)

        if day_price:
            day_income_food = count * day_price['food']
            day_income_spice = count * day_price['spice']
        else:
            day_income_food = None
            day_income_spice = None

        chart_labels.append(d.strftime('%d/%m'))
        # Mask các ngày trong tương lai: chart Xu hướng trong tuần chỉ vẽ tới
        # hôm nay (vd hôm nay T4 → chỉ T2/T3/T4, T5/T6 để trống). Khung "Thực
        # đơn trong tuần" bên dưới vẫn render đủ 5 ngày.
        if d > date.today():
            income_food_data.append(None)
            income_spice_data.append(None)
            expense_food_data.append(None)
            expense_spice_data.append(None)
            balance_food_data.append(None)
            balance_spice_data.append(None)
        else:
            income_food_data.append(day_income_food)
            income_spice_data.append(day_income_spice)
            expense_food_data.append(day_expense_food)
            expense_spice_data.append(day_expense_spice)

            if day_income_food is not None:
                balance_food_data.append(day_income_food - day_expense_food)
                balance_spice_data.append(day_income_spice - day_expense_spice)
            else:
                balance_food_data.append(None)
                balance_spice_data.append(None)

        week_menu_cards.append({
            'date': d,
            'date_str': d.isoformat(),
            'weekday_label': weekday_labels.get(d.weekday(), ''),
            'is_selected': d == selected_date,
            'menu': day_menu,
            'menu_count': day_menu.item_count if day_menu else None,
            'is_registered': d in registration_dates,
        })
    nutrition_result = None
    context = {
        'selected_date': selected_date,
        'selected_date_str': selected_date.isoformat(),
        'registered_count': registered_count,
        'menu': menu,
        'ordered_menu_items': ordered_menu_items,
        'grouped_menu_items': grouped_menu_items,
        'menu_item_count': len(ordered_menu_items) if menu else None,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'meal_price': meal_price,
        'food_price': food_price,
        'spice_price': spice_price,
        'income_food': income_food,
        'income_spice': income_spice,
        'expense_food': expense_food,
        'expense_spice': expense_spice,
        'balance_food': balance_food,
        'balance_spice': balance_spice,
        'chart_labels': chart_labels,
        'income_food_data': income_food_data,
        'income_spice_data': income_spice_data,
        'expense_food_data': expense_food_data,
        'expense_spice_data': expense_spice_data,
        'balance_food_data': balance_food_data,
        'balance_spice_data': balance_spice_data,
        'week_menu_cards': week_menu_cards,
        'purchase_list': purchases_today,
        'week_data': week_data,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
@user_passes_test(can_manage_meal_price)
def meal_price_list(request):
    price_settings = MealPriceSetting.objects.all().order_by('-start_date')
    change_logs = MealPriceChangeLog.objects.select_related(
        'changed_by',
        'meal_price_setting'
    ).all()[:20]

    try:
        selected_year = int(request.GET.get('year', date.today().year))
    except (ValueError, TypeError):
        selected_year = date.today().year

    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year, 12, 31)

    price_settings_for_year = MealPriceSetting.objects.filter(
        start_date__lte=year_end
    ).filter(
        Q(end_date__gte=year_start) | Q(end_date__isnull=True)
    ).order_by('start_date')

    price_map = {}

    for setting in price_settings_for_year:
        start = max(setting.start_date, year_start)

        if setting.end_date:
            end = min(setting.end_date, year_end)
        else:
            end = year_end

        meal = int(setting.meal_price)
        spice = int(setting.spice_price or 0)
        entry = {'meal': meal, 'spice': spice, 'food': meal - spice}

        current = start
        while current <= end:
            price_map[current] = entry
            current += timedelta(days=1)

    # Tô vàng ngày quá khứ đã bị "sửa hậu kỳ":
    # với MỖI change log (cả 'create' lẫn 'update'), tính các ngày trong khoảng
    # mà tại thời điểm log được ghi (`changed_at`) đã thuộc về quá khứ.
    # Loại được các log set giá cho khoảng tương lai, dù thời gian sau đó trôi qua
    # (vì ngày đó >= changed_at, không bị mark).
    today = date.today()
    edited_past_days = set()

    for log in MealPriceChangeLog.objects.all():
        if not log.changed_at:
            continue
        changed_date = log.changed_at.date()

        ranges = [(log.new_start_date, log.new_end_date)]
        if log.action == 'update' and log.old_start_date:
            ranges.append((log.old_start_date, log.old_end_date))

        for s, e in ranges:
            if s is None:
                continue
            range_end = e if e else changed_date
            d = max(s, year_start)
            cap = min(range_end, year_end, changed_date - timedelta(days=1))
            while d <= cap:
                edited_past_days.add(d)
                d += timedelta(days=1)

    month_overview = []

    for month in range(1, 13):
        days_in_month = calendar.monthrange(selected_year, month)[1]
        days = []

        for day in range(1, days_in_month + 1):
            current_date = date(selected_year, month, day)
            entry = price_map.get(current_date)

            days.append({
                'date': current_date,
                'day': day,
                'price': entry['meal'] if entry else None,
                'spice_price': entry['spice'] if entry else None,
                'food_price': entry['food'] if entry else None,
                'has_price': entry is not None,
                'is_edited': current_date in edited_past_days,
            })

        month_overview.append({
            'month': month,
            'days': days,
        })

    year_choices = list(range(date.today().year - 2, date.today().year + 3))

    return render(request, 'core/meal_price_list.html', {
        'price_settings': price_settings,
        'change_logs': change_logs,
        'selected_year': selected_year,
        'year_choices': year_choices,
        'month_overview': month_overview,
    })

@login_required
@user_passes_test(can_manage_meal_price)
def meal_price_create(request):
    if request.method == 'POST':
        form = MealPriceSettingForm(request.POST)
        if form.is_valid():
            price_setting = form.save()

            MealPriceChangeLog.objects.create(
                meal_price_setting=price_setting,
                action='create',
                new_start_date=price_setting.start_date,
                new_end_date=price_setting.end_date,
                new_meal_price=price_setting.meal_price,
                new_spice_price=price_setting.spice_price,
                reason=form.cleaned_data['reason'],
                changed_by=request.user,
            )

            messages.success(request, 'Đã tạo cấu hình giá suất ăn mới.')
            return redirect('meal_price_list')
    else:
        form = MealPriceSettingForm()

    return render(request, 'core/meal_price_form.html', {
        'form': form,
        'page_title': 'Thêm giá suất ăn',
        'submit_label': 'Lưu giá suất ăn',
    })


@login_required
@user_passes_test(can_manage_meal_price)
def meal_price_update(request, pk):
    price_setting = get_object_or_404(MealPriceSetting, pk=pk)

    old_start_date = price_setting.start_date
    old_end_date = price_setting.end_date
    old_meal_price = price_setting.meal_price
    old_spice_price = price_setting.spice_price

    if request.method == 'POST':
        form = MealPriceSettingForm(request.POST, instance=price_setting)
        if form.is_valid():
            updated_setting = form.save()

            MealPriceChangeLog.objects.create(
                meal_price_setting=updated_setting,
                action='update',
                old_start_date=old_start_date,
                old_end_date=old_end_date,
                old_meal_price=old_meal_price,
                old_spice_price=old_spice_price,
                new_start_date=updated_setting.start_date,
                new_end_date=updated_setting.end_date,
                new_meal_price=updated_setting.meal_price,
                new_spice_price=updated_setting.spice_price,
                reason=form.cleaned_data['reason'],
                changed_by=request.user,
            )

            messages.success(request, 'Đã cập nhật cấu hình giá suất ăn.')
            return redirect('meal_price_list')
    else:
        form = MealPriceSettingForm(instance=price_setting)

    return render(request, 'core/meal_price_form.html', {
        'form': form,
        'page_title': 'Cập nhật giá suất ăn',
        'submit_label': 'Cập nhật',
    })
@login_required
def nutrition_analysis_api(request):
    selected_date = timezone.localdate()

    nutrition_obj = DailyNutritionAnalysis.objects.filter(
        date=selected_date
    ).first()

    if nutrition_obj:
        return JsonResponse(nutrition_obj.raw_json)

    menu = DailyMenu.objects.filter(date=selected_date).first()

    if not menu:
        return JsonResponse({
            "error": "Không có menu"
        })

    ordered_menu_items = menu.items.select_related(
        'dish'
    ).prefetch_related(
        'dish__ingredients__ingredient'
    )

    nutrition_input = []

    for item in ordered_menu_items:
        dish = item.dish

        ingredients = []

        for ing in dish.ingredients.all():
            ingredients.append({
                "name": ing.ingredient.name,
                "grams": float(ing.quantity_per_person),
                "unit": ing.unit,
            })

        nutrition_input.append({
            "dish": dish.name,
            "ingredients": ingredients,
        })

    now = timezone.localtime()

    if now.time() < time(8, 0):
        return JsonResponse({
            "error": "Chưa đến thời gian phân tích"
        })

    try:
        result = estimate_nutrition(nutrition_input)

        DailyNutritionAnalysis.objects.create(
            date=selected_date,
            total_kcal=result.get("total_kcal", 0),
            level=result.get("level", ""),
            summary=result.get("summary", ""),
            raw_json=result,
        )

        return JsonResponse(result)

    except Exception as e:
        print("AI ERROR:", e)

        return JsonResponse({
            "error": "AI tạm thời bận"
        })
from django.db import models

# --- Tích hợp hệ thống nhận diện (camera) ---
# Ngưỡng coi camera là offline khi không nhận heartbeat (giây).
RECOGNITION_OFFLINE_SECONDS = 30


def _get_recognition_token():
    cfg = SystemConfig.objects.filter(key='recognition_token').first()
    return (cfg.value or '').strip() if cfg else ''


def _check_recognition_auth(request):
    """Xác thực request từ hệ thống nhận diện qua header
    `Authorization: Bearer <token>`.

    Nếu admin chưa cấu hình `recognition_token` (rỗng) → trả True (chưa
    enforce) để không làm vỡ luồng điểm danh ngay sau khi deploy. Chỉ khi
    token đã được set thì mới bắt buộc khớp."""
    expected = _get_recognition_token()
    if not expected:
        return True
    auth = request.headers.get('Authorization', '')
    token = auth[7:].strip() if auth.startswith('Bearer ') else ''
    return token == expected


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile) and getattr(profile, 'role', '').lower() == 'admin'


def _log_camera_status(camera_id, status, changed_at):
    """Ghi 1 dòng lịch sử chuyển trạng thái — chỉ ghi nếu khác trạng thái
    gần nhất (tránh ghi trùng khi gọi nhiều lần)."""
    last = CameraStatusLog.objects.filter(camera_id=camera_id).order_by('-changed_at').first()
    if last and last.status == status:
        return
    CameraStatusLog.objects.create(camera_id=camera_id, status=status, changed_at=changed_at)


@csrf_exempt
def recognition_heartbeat_api(request):
    """Nhận heartbeat từ client nhận diện. Body JSON:
    {"camera_id": "bep_kv2", "info": {...optional...}}.
    Token gửi qua header Authorization: Bearer <token>."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST method required"}, status=405)
    if not _check_recognition_auth(request):
        return JsonResponse({"success": False, "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    camera_id = (data.get('camera_id') or '').strip()
    if not camera_id:
        return JsonResponse({"success": False, "message": "camera_id required"}, status=400)

    now = timezone.now()

    # Trạng thái trước đó để biết có phải transition offline → online không
    hb = RecognitionHeartbeat.objects.filter(camera_id=camera_id).first()
    was_online = bool(hb) and (now - hb.last_heartbeat_at).total_seconds() < RECOGNITION_OFFLINE_SECONDS

    RecognitionHeartbeat.objects.update_or_create(
        camera_id=camera_id,
        defaults={'last_heartbeat_at': now, 'last_info': data.get('info')},
    )

    if not was_online:
        _log_camera_status(camera_id, 'online', now)

    return JsonResponse({"success": True})


@login_required
def recognition_status_api(request):
    """Trả trạng thái online/offline các camera nhận diện — chỉ admin.
    Đồng thời phát hiện camera vừa rớt offline (lazy) và ghi log với
    timestamp thực tế = heartbeat cuối + ngưỡng."""
    if not _is_admin(request.user):
        return JsonResponse({"success": False, "message": "Forbidden"}, status=403)

    now = timezone.now()
    cameras = []
    for hb in RecognitionHeartbeat.objects.all():
        elapsed = (now - hb.last_heartbeat_at).total_seconds()
        online = elapsed < RECOGNITION_OFFLINE_SECONDS
        if not online:
            last = CameraStatusLog.objects.filter(
                camera_id=hb.camera_id).order_by('-changed_at').first()
            if last and last.status == 'online':
                offline_at = hb.last_heartbeat_at + timedelta(seconds=RECOGNITION_OFFLINE_SECONDS)
                _log_camera_status(hb.camera_id, 'offline', offline_at)
        cameras.append({
            'camera_id': hb.camera_id,
            'online': online,
            'last_seen': hb.last_heartbeat_at.isoformat(),
            'seconds_since': int(elapsed),
        })
    cameras.sort(key=lambda c: c['camera_id'])
    return JsonResponse({"success": True, "cameras": cameras})


@login_required
def recognition_logs_api(request):
    """Trả lịch sử bật/tắt camera nhận diện — chỉ admin. Lấy trong 5 ngày
    gần nhất, tối đa 10 dòng mới nhất."""
    if not _is_admin(request.user):
        return JsonResponse({"success": False, "message": "Forbidden"}, status=403)

    since = timezone.now() - timedelta(days=5)
    logs = CameraStatusLog.objects.filter(
        changed_at__gte=since).order_by('-changed_at')[:10]
    items = [{
        'camera_id': lg.camera_id,
        'status': lg.status,
        'changed_at': timezone.localtime(lg.changed_at).strftime('%H:%M  %d/%m/%Y'),
    } for lg in logs]
    return JsonResponse({"success": True, "logs": items})


CAPTURE_RETENTION_DAYS = 30


def _purge_old_captures_if_due():
    """Xóa ảnh chụp nhận diện cũ hơn CAPTURE_RETENTION_DAYS — chạy tối đa
    1 lần/ngày, được kích bởi request capture đầu tiên trong ngày (không cần
    cron/systemd timer riêng)."""
    today = timezone.localdate().isoformat()
    cfg = SystemConfig.objects.filter(key='capture_purge_date').first()
    if cfg and cfg.value == today:
        return
    cutoff = timezone.now() - timedelta(days=CAPTURE_RETENTION_DAYS)
    for cap in AttendanceCapture.objects.filter(scan_time__lt=cutoff):
        if cap.image:
            cap.image.delete(save=False)  # xóa file vật lý
        cap.delete()
    SystemConfig.objects.update_or_create(
        key='capture_purge_date', defaults={'value': today})


@csrf_exempt
def recognition_capture_api(request):
    """Nhận ảnh chụp khung hình lúc nhận diện 1 nhân viên (multipart/form-data).
    Fields: image (file, bắt buộc), employee_code (bắt buộc), camera_id,
    scan_time, status, score. Token qua header Authorization: Bearer."""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST method required"}, status=405)
    if not _check_recognition_auth(request):
        return JsonResponse({"success": False, "message": "Unauthorized"}, status=401)

    image = request.FILES.get('image')
    employee_code = (request.POST.get('employee_code') or '').strip()
    if not image or not employee_code:
        return JsonResponse(
            {"success": False, "message": "image và employee_code là bắt buộc"}, status=400)

    scan_time = parse_datetime(request.POST.get('scan_time') or '') or timezone.now()

    score_raw = (request.POST.get('score') or '').strip()
    try:
        score = float(score_raw) if score_raw else None
    except ValueError:
        score = None

    AttendanceCapture.objects.create(
        employee_code=employee_code,
        camera_id=(request.POST.get('camera_id') or '').strip(),
        scan_time=scan_time,
        status=(request.POST.get('status') or '').strip(),
        score=score,
        image=image,
    )

    _purge_old_captures_if_due()
    return JsonResponse({"success": True})


@csrf_exempt
def attendance_log_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST method required"}, status=405)
    if not _check_recognition_auth(request):
        return JsonResponse({"success": False, "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    if isinstance(data, dict):
        data = [data]  # convert single record to list

    created = 0
    updated = 0
    skipped = 0
    for rec in data:
        try:
            scan_time = parse_datetime(rec.get("scan_time"))
            if not scan_time:
                continue

            emp_code = (rec.get("employee_code") or "").strip()
            if not emp_code:
                continue

            new_status = rec.get("status", "Chưa đăng ký")

            existing = AttendanceLog.objects.filter(
                employee_code=emp_code,
                scan_time__date=scan_time.date(),
            ).first()

            if existing:
                # Trùng cùng ngày: nếu trạng thái khác (vd not_registered -> valid sau khi
                # nhân viên đăng ký bù) thì cập nhật. Trùng và cùng trạng thái → bỏ qua.
                if existing.status != new_status:
                    existing.status = new_status
                    existing.scan_time = scan_time
                    if rec.get("full_name"):
                        existing.full_name = rec["full_name"]
                    existing.save(update_fields=["status", "scan_time", "full_name"])
                    updated += 1
                else:
                    skipped += 1
                continue

            AttendanceLog.objects.create(
                employee_code=emp_code,
                full_name=rec.get("full_name", ""),
                scan_time=scan_time,
                type=rec.get("type", "bếp ăn"),
                status=new_status,
            )
            created += 1
        except Exception as e:
            print(f"AttendanceLog error: {e}")
            continue

    return JsonResponse({
        "success": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
    })