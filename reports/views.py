#report/views
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.db.models import Sum
from finance.models import DailyPurchase
from core.views import get_registered_count, get_meal_price_for_date
from accounts.permissions import can_view_report, can_export_report
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
        'can_export_report': can_export_report(request.user),
    }
    return render(request, 'reports/report_dashboard.html', context)


# ================================================================
# EXPORT VIEWS
# ================================================================
import io
from calendar import monthrange
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from finance.models import PurchaseExtraItem
from reviews.models import DishReview, MealReview
from django.db.models import Count, Q


# ---------- helpers ----------
HEADER_FILL  = PatternFill("solid", fgColor="1E40AF")
HEADER_FONT  = Font(bold=True, color="FFFFFF", size=11)
TOTAL_FILL   = PatternFill("solid", fgColor="DBEAFE")
TOTAL_FONT   = Font(bold=True, size=11)
SUBHEAD_FILL = PatternFill("solid", fgColor="EFF6FF")
CENTER       = Alignment(horizontal="center", vertical="center")
WRAP         = Alignment(wrap_text=True, vertical="top")

thin = Side(style="thin", color="CBD5E1")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)


def _fmt_vnd(val):
    if val is None: return ""
    return f"{int(val):,}".replace(",", ".")


def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value or "")))
            except:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)


def _header_row(ws, cols, row=1):
    for c, title in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=title)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER


def _get_period(request, prefix=""):
    """Parse period params; returns (period, start_date, end_date, label)."""
    today = date.today()
    period = request.GET.get(f"{prefix}period", "month")
    try: sel_date = date.fromisoformat(request.GET.get(f"{prefix}date", today.isoformat()))
    except: sel_date = today
    try: sel_month = int(request.GET.get(f"{prefix}month", today.month))
    except: sel_month = today.month
    try: sel_year  = int(request.GET.get(f"{prefix}year",  today.year))
    except: sel_year  = today.year

    if period == "week":
        start = sel_date - timedelta(days=sel_date.weekday())
        end   = start + timedelta(days=6)
        label = f"tuan_{start.strftime('%d%m%Y')}_{end.strftime('%d%m%Y')}"
    elif period == "month":
        start = date(sel_year, sel_month, 1)
        end   = date(sel_year, sel_month, monthrange(sel_year, sel_month)[1])
        label = f"thang_{sel_month:02d}_{sel_year}"
    elif period == "year":
        start = date(sel_year, 1, 1)
        end   = date(sel_year, 12, 31)
        label = f"nam_{sel_year}"
    else:  # day
        start = end = sel_date
        label = f"ngay_{sel_date.strftime('%d%m%Y')}"

    return period, start, end, label, sel_year, sel_month


# ================================================================
# 1. BÁO CÁO THU – CHI
# ================================================================
@login_required
@user_passes_test(can_export_report)
def export_revenue_report(request):
    period, start_date, end_date, label, sel_year, sel_month = _get_period(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Thu - Chi"

    title_text = f"BÁO CÁO THU – CHI  ({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')})"
    ws.merge_cells("A1:F1")
    t = ws["A1"]
    t.value = title_text
    t.font = Font(bold=True, size=13, color="1E40AF")
    t.alignment = CENTER
    ws.row_dimensions[1].height = 28

    if period == "year":
        # Xuất theo tháng
        cols = ["Tháng", "Tổng người ĐK", "Tổng thu (VNĐ)", "Tổng chi (VNĐ)", "Chênh lệch (VNĐ)"]
        _header_row(ws, cols, row=2)
        ws.row_dimensions[2].height = 20

        grand_income = grand_expense = grand_balance = 0
        row_idx = 3
        for m in range(1, 13):
            ms = date(sel_year, m, 1)
            me = date(sel_year, m, monthrange(sel_year, m)[1])
            m_income = m_expense = m_people = 0
            d = ms
            while d <= me:
                cnt = get_registered_count(d)
                price = get_meal_price_for_date(d)
                if cnt and price:
                    m_income += cnt * price
                    m_people += cnt
                d += timedelta(days=1)

            cost_agg = DailyPurchase.objects.filter(
                date__range=(ms, me), status=DailyPurchase.STATUS_APPROVED
            ).aggregate(s=Sum('actual_cost'))['s'] or 0
            m_expense = int(cost_agg)
            m_balance = m_income - m_expense

            grand_income  += m_income
            grand_expense += m_expense
            grand_balance += m_balance

            row_data = [f"Tháng {m}/{sel_year}", m_people, _fmt_vnd(m_income), _fmt_vnd(m_expense), _fmt_vnd(m_balance)]
            for c, v in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.border = BORDER
                cell.alignment = CENTER if c != 1 else Alignment(horizontal="left", vertical="center")
                if m_balance < 0:
                    cell.font = Font(color="DC2626")
            row_idx += 1

        # Dòng tổng kết
        for c, v in enumerate(["TỔNG KẾT", "", _fmt_vnd(grand_income), _fmt_vnd(grand_expense), _fmt_vnd(grand_balance)], 1):
            cell = ws.cell(row=row_idx, column=c, value=v)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = BORDER
            cell.alignment = CENTER

    else:
        # Xuất theo ngày (tuần/tháng)
        cols = ["Ngày", "Thứ", "Số người ĐK", "Giá suất (VNĐ)", "Thu (VNĐ)", "Chi (VNĐ)", "Chênh lệch (VNĐ)"]
        _header_row(ws, cols, row=2)
        ws.row_dimensions[2].height = 20

        WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
        grand_income = grand_expense = grand_balance = 0
        row_idx = 3
        d = start_date
        while d <= end_date:
            cnt   = get_registered_count(d)
            price = get_meal_price_for_date(d)
            cost_agg = DailyPurchase.objects.filter(
                date=d, status=DailyPurchase.STATUS_APPROVED
            ).aggregate(s=Sum('actual_cost'))['s']
            cost = int(cost_agg or 0) if cost_agg else None

            income  = (cnt * price) if (cnt and price) else None
            balance = (income - cost) if (income is not None and cost is not None) else None

            if income:  grand_income  += income
            if cost:    grand_expense += cost
            if balance: grand_balance += balance

            row_data = [
                d.strftime("%d/%m/%Y"),
                WEEKDAYS[d.weekday()],
                cnt or "",
                _fmt_vnd(price),
                _fmt_vnd(income),
                _fmt_vnd(cost),
                _fmt_vnd(balance),
            ]
            for c, v in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.border = BORDER
                cell.alignment = CENTER if c > 1 else Alignment(horizontal="left", vertical="center")
                if balance is not None and balance < 0:
                    cell.font = Font(color="DC2626")
            row_idx += 1
            d += timedelta(days=1)

        # Tổng kết
        for c, v in enumerate(["TỔNG KẾT", "", "", "", _fmt_vnd(grand_income), _fmt_vnd(grand_expense), _fmt_vnd(grand_balance)], 1):
            cell = ws.cell(row=row_idx, column=c, value=v)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = BORDER
            cell.alignment = CENTER

    _auto_width(ws)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="bao_cao_thu_chi_{label}.xlsx"'
    return response


# ================================================================
# 2. BÁO CÁO CHI PHÍ
# ================================================================
@login_required
@user_passes_test(can_export_report)
def export_cost_report(request):
    period, start_date, end_date, label, sel_year, sel_month = _get_period(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Chi phí"

    title_text = f"BÁO CÁO CHI PHÍ  ({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')})"
    ws.merge_cells("A1:G1")
    t = ws["A1"]
    t.value = title_text
    t.font = Font(bold=True, size=13, color="1E40AF")
    t.alignment = CENTER
    ws.row_dimensions[1].height = 28

    if period in ("day", "week"):
        # Chi tiết từng mặt hàng
        cols = ["Ngày", "Loại mua", "Tên mặt hàng", "Số lượng", "Đơn vị", "Đơn giá (VNĐ)", "Thành tiền (VNĐ)"]
        _header_row(ws, cols, row=2)

        items = PurchaseExtraItem.objects.filter(
            date__range=(start_date, end_date),
            purchase__status=DailyPurchase.STATUS_APPROVED
        ).select_related("purchase").order_by("date", "purchase_id")

        row_idx = 3
        grand_total = 0
        for item in items:
            total_line = float(item.quantity or 0) * float(item.unit_price or 0)
            grand_total += total_line
            row_data = [
                item.date.strftime("%d/%m/%Y"),
                item.purchase.get_purchase_type_display(),
                item.ingredient_name,
                float(item.quantity or 0),
                item.unit or "",
                _fmt_vnd(item.unit_price),
                _fmt_vnd(total_line),
            ]
            for c, v in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.border = BORDER
                cell.alignment = CENTER if c in (4, 5, 6, 7) else Alignment(horizontal="left", vertical="center")
            row_idx += 1

        # Phiếu không có chi tiết (chưa quét AI)
        purchases_no_items = DailyPurchase.objects.filter(
            date__range=(start_date, end_date),
            status=DailyPurchase.STATUS_APPROVED,
            extra_items__isnull=True
        ).distinct()
        for p in purchases_no_items:
            row_data = [p.date.strftime("%d/%m/%Y"), p.get_purchase_type_display(), "(Chưa quét AI – chỉ có tổng)", "", "", "", _fmt_vnd(p.actual_cost)]
            grand_total += float(p.actual_cost or 0)
            for c, v in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.border = BORDER
                cell.font = Font(italic=True, color="6B7280")
                cell.alignment = Alignment(horizontal="left", vertical="center")
            row_idx += 1

        # Tổng
        for c, v in enumerate(["TỔNG CHI PHÍ", "", "", "", "", "", _fmt_vnd(grand_total)], 1):
            cell = ws.cell(row=row_idx, column=c, value=v)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = BORDER
            cell.alignment = CENTER

    else:
        # Tháng/Năm: tổng hợp
        if period == "year":
            cols = ["Tháng", "Số phiếu chi", "Tổng chi phí (VNĐ)"]
            _header_row(ws, cols, row=2)
            row_idx = 3
            grand = 0
            for m in range(1, 13):
                ms = date(sel_year, m, 1)
                me = date(sel_year, m, monthrange(sel_year, m)[1])
                agg = DailyPurchase.objects.filter(date__range=(ms, me), status=DailyPurchase.STATUS_APPROVED).aggregate(
                    total=Sum('actual_cost'), cnt=Count('id'))
                total = int(agg['total'] or 0)
                cnt   = agg['cnt'] or 0
                grand += total
                for c, v in enumerate([f"Tháng {m}/{sel_year}", cnt, _fmt_vnd(total)], 1):
                    cell = ws.cell(row=row_idx, column=c, value=v)
                    cell.border = BORDER
                    cell.alignment = CENTER
                row_idx += 1
            for c, v in enumerate(["TỔNG KẾT", "", _fmt_vnd(grand)], 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.fill = TOTAL_FILL; cell.font = TOTAL_FONT; cell.border = BORDER; cell.alignment = CENTER
        else:
            # month
            cols = ["Ngày", "Loại mua", "Số phiếu", "Tổng chi (VNĐ)"]
            _header_row(ws, cols, row=2)
            row_idx = 3
            grand = 0
            d = start_date
            while d <= end_date:
                agg = DailyPurchase.objects.filter(date=d, status=DailyPurchase.STATUS_APPROVED).aggregate(
                    total=Sum('actual_cost'), cnt=Count('id'))
                if agg['cnt']:
                    total = int(agg['total'] or 0)
                    grand += total
                    for c, v in enumerate([d.strftime("%d/%m/%Y"), "Tất cả", agg['cnt'], _fmt_vnd(total)], 1):
                        cell = ws.cell(row=row_idx, column=c, value=v)
                        cell.border = BORDER; cell.alignment = CENTER
                    row_idx += 1
                d += timedelta(days=1)
            for c, v in enumerate(["TỔNG KẾT", "", "", _fmt_vnd(grand)], 1):
                cell = ws.cell(row=row_idx, column=c, value=v)
                cell.fill = TOTAL_FILL; cell.font = TOTAL_FONT; cell.border = BORDER; cell.alignment = CENTER

    _auto_width(ws)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="bao_cao_chi_phi_{label}.xlsx"'
    return response


# ================================================================
# 3. BÁO CÁO ĐÁNH GIÁ MÓN ĂN
# ================================================================
@login_required
@user_passes_test(can_export_report)
def export_review_report(request):
    period, start_date, end_date, label, sel_year, sel_month = _get_period(request)

    wb = openpyxl.Workbook()

    # ---- Sheet 1: Thống kê Like/Dislike ----
    ws1 = wb.active
    ws1.title = "Thống kê đánh giá"

    title_text = f"BÁO CÁO ĐÁNH GIÁ MÓN ĂN  ({start_date.strftime('%d/%m/%Y')} – {end_date.strftime('%d/%m/%Y')})"
    ws1.merge_cells("A1:F1")
    t = ws1["A1"]
    t.value = title_text
    t.font = Font(bold=True, size=13, color="1E40AF")
    t.alignment = CENTER
    ws1.row_dimensions[1].height = 28

    cols = ["Tên món ăn", "Tổng lượt Like 👍", "Tổng lượt Dislike 👎", "Tổng đánh giá", "Tỉ lệ hài lòng (%)"]
    _header_row(ws1, cols, row=2)

    dish_stats = DishReview.objects.filter(
        meal_review__date__range=(start_date, end_date)
    ).values("dish__name").annotate(
        likes    = Count("id", filter=Q(evaluation="like")),
        dislikes = Count("id", filter=Q(evaluation="dislike")),
        total    = Count("id"),
    ).order_by("-likes")

    row_idx = 3
    for stat in dish_stats:
        pct = round(stat['likes'] / stat['total'] * 100, 1) if stat['total'] else 0
        row_data = [stat['dish__name'], stat['likes'], stat['dislikes'], stat['total'], f"{pct}%"]
        for c, v in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=c, value=v)
            cell.border = BORDER
            cell.alignment = CENTER if c > 1 else Alignment(horizontal="left", vertical="center")
            if c == 5:
                if pct >= 70:
                    cell.font = Font(color="16A34A", bold=True)
                elif pct < 50:
                    cell.font = Font(color="DC2626", bold=True)
        row_idx += 1

    _auto_width(ws1)

    # ---- Sheet 2: Chi tiết góp ý ----
    ws2 = wb.create_sheet("Chi tiết góp ý")
    ws2.merge_cells("A1:C1")
    t2 = ws2["A1"]
    t2.value = "CHI TIẾT GÓP Ý TYPING"
    t2.font = Font(bold=True, size=13, color="1E40AF")
    t2.alignment = CENTER
    ws2.row_dimensions[1].height = 28

    _header_row(ws2, ["Ngày", "Người đánh giá", "Nội dung góp ý"], row=2)

    comments = MealReview.objects.filter(
        date__range=(start_date, end_date)
    ).exclude(comment="").select_related("user").order_by("-date")

    row_idx = 3
    for review in comments:
        user_display = review.user.username if review.user else "Ẩn danh"
        row_data = [review.date.strftime("%d/%m/%Y"), user_display, review.comment]
        for c, v in enumerate(row_data, 1):
            cell = ws2.cell(row=row_idx, column=c, value=v)
            cell.border = BORDER
            cell.alignment = WRAP if c == 3 else Alignment(horizontal="left", vertical="top")
        ws2.row_dimensions[row_idx].height = max(30, min(len(review.comment) // 3, 120))
        row_idx += 1

    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 20
    ws2.column_dimensions["C"].width = 60

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(buf, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="bao_cao_danh_gia_{label}.xlsx"'
    return response