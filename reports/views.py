#report/views
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.db.models import Sum
from finance.models import DailyPurchase
from core.views import get_registered_count, get_meal_price_for_date
from accounts.permissions import can_view_report
def staff_required(user):
    return user.is_staff or user.is_superuser


def build_purchase_map(start_date, end_date):
    rows = DailyPurchase.objects.filter(
        date__range=(start_date, end_date),
        status=DailyPurchase.STATUS_APPROVED
    ).values('date').annotate(
        total_cost=Sum('actual_cost')
    )

    return {
        row['date']: int(row['total_cost'] or 0)
        for row in rows
    }


@login_required
@user_passes_test(can_view_report)
def report_dashboard(request):
    today = date.today()

    form_type = request.GET.get('form_type', 'main')

    # =========================
    # FORM 1: BÁO CÁO TỔNG HỢP
    # =========================
    if form_type == 'main':
        view_type = request.GET.get('view_type', 'month')

        try:
            selected_month = int(request.GET.get('month', today.month))
        except (ValueError, TypeError):
            selected_month = today.month

        try:
            selected_year = int(request.GET.get('year', today.year))
        except (ValueError, TypeError):
            selected_year = today.year

        if selected_month < 1 or selected_month > 12:
            selected_month = today.month

        try:
            selected_date_str = request.GET.get('selected_date')
            selected_date = date.fromisoformat(selected_date_str) if selected_date_str else today
        except ValueError:
            selected_date = today

        balance_chart_type = request.GET.get('balance_chart_type', 'daily_in_month')

    # =========================
    # FORM 2: BIỂU ĐỒ CHÊNH LỆCH
    # =========================
    else:
        view_type = request.GET.get('view_type_state', 'month')

        try:
            selected_month = int(request.GET.get('month_state', today.month))
        except (ValueError, TypeError):
            selected_month = today.month

        try:
            selected_year = int(request.GET.get('year_state', today.year))
        except (ValueError, TypeError):
            selected_year = today.year

        if selected_month < 1 or selected_month > 12:
            selected_month = today.month

        try:
            selected_date_str = request.GET.get('selected_date_state')
            selected_date = date.fromisoformat(selected_date_str) if selected_date_str else today
        except ValueError:
            selected_date = today

        balance_chart_type = request.GET.get('balance_chart_type', 'daily_in_month')

    # =========================
    # XÁC ĐỊNH KHOẢNG THỜI GIAN CHÍNH
    # =========================
    if view_type == 'week':
        start_date = selected_date - timedelta(days=selected_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = date(selected_year, selected_month, 1)
        end_day = monthrange(selected_year, selected_month)[1]
        end_date = date(selected_year, selected_month, end_day)

    purchase_map = build_purchase_map(start_date, end_date)
    purchase_detail_map = {}

    all_purchases = DailyPurchase.objects.filter(
        date__range=(start_date, end_date),
        status=DailyPurchase.STATUS_APPROVED
    ).select_related('created_by')

    for p in all_purchases:
        purchase_detail_map.setdefault(p.date, []).append(p)

    daily_rows = []
    chart_labels = []
    income_data = []
    expense_data = []
    balance_data = []

    total_income = 0
    total_expense = 0
    total_balance = 0

    current_date = start_date
    while current_date <= end_date:
        registered_count = get_registered_count(current_date)
        meal_price = get_meal_price_for_date(current_date)
        actual_cost = purchase_map.get(current_date)

        if registered_count is not None and meal_price is not None:
            income = registered_count * meal_price
        else:
            income = None

        expense = actual_cost if actual_cost is not None else None

        if income is not None and expense is not None:
            balance = income - expense
        else:
            balance = None

        row = {
            'date': current_date,
            'registered_count': registered_count,
            'meal_price': meal_price,
            'income': income,
            'expense': expense,
            'balance': balance,
            'purchase_list': purchase_detail_map.get(current_date, []),
        }
        daily_rows.append(row)

        chart_labels.append(current_date.strftime('%d/%m'))
        income_data.append(income)
        expense_data.append(expense)
        balance_data.append(balance)

        if income is not None:
            total_income += income

        if expense is not None:
            total_expense += expense

        if balance is not None:
            total_balance += balance

        current_date += timedelta(days=1)

    # =========================
    # BIỂU ĐỒ CHÊNH LỆCH RIÊNG
    # =========================
    balance_chart_labels = []
    balance_chart_values = []

    if balance_chart_type == 'monthly_in_year':
        year_start = date(selected_year, 1, 1)
        year_end = date(selected_year, 12, 31)
        year_purchase_map = build_purchase_map(year_start, year_end)

        for month in range(1, 13):
            month_start = date(selected_year, month, 1)
            month_end = date(selected_year, month, monthrange(selected_year, month)[1])

            month_balance = 0
            d = month_start
            while d <= month_end:
                registered_count = get_registered_count(d)
                meal_price = get_meal_price_for_date(d)
                actual_cost = year_purchase_map.get(d)

                if registered_count is not None and meal_price is not None:
                    income = registered_count * meal_price
                else:
                    income = None

                if income is not None and actual_cost is not None:
                    day_balance = income - actual_cost
                    month_balance += day_balance

                d += timedelta(days=1)

            balance_chart_labels.append(f'T{month}')
            balance_chart_values.append(month_balance)
    else:
        month_start = date(selected_year, selected_month, 1)
        month_end = date(selected_year, selected_month, monthrange(selected_year, selected_month)[1])
        month_purchase_map = build_purchase_map(month_start, month_end)

        d = month_start
        while d <= month_end:
            registered_count = get_registered_count(d)
            meal_price = get_meal_price_for_date(d)
            actual_cost = month_purchase_map.get(d)

            if registered_count is not None and meal_price is not None:
                income = registered_count * meal_price
            else:
                income = None

            if income is not None and actual_cost is not None:
                balance = income - actual_cost
            else:
                balance = None

            balance_chart_labels.append(d.strftime('%d/%m'))
            balance_chart_values.append(balance)
            d += timedelta(days=1)

    month_choices = list(range(1, 13))
    year_choices = list(range(today.year - 2, today.year + 3))

    context = {
        'form_type': form_type,
        'view_type': view_type,
        'balance_chart_type': balance_chart_type,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_date': selected_date.isoformat() if selected_date else '',
        'month_choices': month_choices,
        'year_choices': year_choices,
        'daily_rows': daily_rows,
        'total_income': total_income,
        'total_expense': total_expense,
        'total_balance': total_balance,
        'chart_labels': chart_labels,
        'income_data': income_data,
        'expense_data': expense_data,
        'balance_data': balance_data,
        'balance_chart_labels': balance_chart_labels,
        'balance_chart_values': balance_chart_values,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/report_dashboard.html', context)