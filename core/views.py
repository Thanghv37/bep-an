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
from .models import AttendanceLog
from django.utils.dateparse import parse_datetime

def get_registered_count(target_date):
    total = MealRegistration.objects.filter(
        date=target_date
    ).aggregate(total=Sum('quantity'))['total']

    return total or 0


def get_meal_price_for_date(target_date):
    price_setting = MealPriceSetting.objects.filter(
        start_date__lte=target_date
    ).order_by('-start_date').first()

    if not price_setting:
        return None

    if price_setting.end_date is None:
        return int(price_setting.meal_price)

    if price_setting.start_date <= target_date <= price_setting.end_date:
        return int(price_setting.meal_price)

    return None


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

    meal_price = get_meal_price_for_date(selected_date)
    registered_count = get_registered_count(selected_date)

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
        

        # 1. sort menu trước
        ordered_menu_items = sorted(
            menu.items.all(),
            key=lambda item: (
                dish_type_order.get(item.dish.dish_type, 99),
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

    actual_cost = purchases_today.aggregate(total=Sum('actual_cost'))['total']

    if registered_count is not None and meal_price is not None:
        total_income = registered_count * meal_price
    else:
        total_income = None

    total_expense = actual_cost

    if total_income is not None and total_expense is not None:
        balance = total_income - total_expense
    else:
        balance = None

    chart_labels = []
    income_data = []
    expense_data = []
    balance_data = []

    # Xác định thứ 2 của tuần chứa selected_date
    start_of_week = selected_date - timedelta(days=selected_date.weekday())

    # Chỉ hiển thị 5 ngày làm việc: thứ 2 -> thứ 6
    week_days = [start_of_week + timedelta(days=i) for i in range(5)]

    purchases = DailyPurchase.objects.filter(date__range=(week_days[0], week_days[-1]),status=DailyPurchase.STATUS_APPROVED)
    purchase_map = {
        item['date']: int(item['total_cost'] or 0)
        for item in DailyPurchase.objects.filter(
            date__range=(week_days[0], week_days[-1]),
            status=DailyPurchase.STATUS_APPROVED
        ).values('date').annotate(total_cost=Sum('actual_cost'))
    }

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
        price = get_meal_price_for_date(d)
        cost = purchase_map.get(d)
        day_menu = week_menu_map.get(d)

        if count is not None and price is not None:
            income = count * price
        else:
            income = None

        if income is not None and cost is not None:
            diff = income - cost
        else:
            diff = None

        chart_labels.append(d.strftime('%d/%m'))
        income_data.append(income)
        expense_data.append(cost)
        balance_data.append(diff)

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
        'chart_labels': chart_labels,
        'income_data': income_data,
        'expense_data': expense_data,
        'balance_data': balance_data,
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

        current = start
        while current <= end:
            price_map[current] = int(setting.meal_price)
            current += timedelta(days=1)

    month_overview = []

    for month in range(1, 13):
        days_in_month = calendar.monthrange(selected_year, month)[1]
        days = []

        for day in range(1, days_in_month + 1):
            current_date = date(selected_year, month, day)
            price = price_map.get(current_date)

            days.append({
                'date': current_date,
                'day': day,
                'price': price,
                'has_price': price is not None,
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
                new_start_date=updated_setting.start_date,
                new_end_date=updated_setting.end_date,
                new_meal_price=updated_setting.meal_price,
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

@csrf_exempt
def attendance_log_api(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST method required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    if isinstance(data, dict):
        data = [data]  # convert single record to list

    created = 0
    skipped = 0
    for rec in data:
        try:
            scan_time = parse_datetime(rec.get("scan_time"))
            if not scan_time:
                continue

            emp_code = (rec.get("employee_code") or "").strip()
            if not emp_code:
                continue

            # Bỏ qua nếu nhân viên này đã có log trong cùng ngày — chỉ giữ lần quét đầu
            if AttendanceLog.objects.filter(
                employee_code=emp_code,
                scan_time__date=scan_time.date(),
            ).exists():
                skipped += 1
                continue

            AttendanceLog.objects.create(
                employee_code=emp_code,
                full_name=rec.get("full_name", ""),
                scan_time=scan_time,
                type=rec.get("type", "bếp ăn"),
                status=rec.get("status", "Chưa đăng ký")
            )
            created += 1
        except Exception as e:
            print(f"AttendanceLog error: {e}")
            continue

    return JsonResponse({"success": True, "created": created, "skipped": skipped})