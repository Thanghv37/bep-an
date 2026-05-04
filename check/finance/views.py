from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from accounts.permissions import is_admin, is_kitchen
from django.contrib import messages
from datetime import date
from django.http import JsonResponse
from django.db.models import Sum

from .models import DailyPurchase, PurchaseExtraItem
from .forms import DailyPurchaseForm
from meals.models import DailyMenu


def can_manage_purchase(user):
    return is_admin(user) or is_kitchen(user)


# =========================
# LIST
# =========================
@login_required
@user_passes_test(can_manage_purchase)
def purchase_list(request):
    today = date.today()

    try:
        selected_year = int(request.GET.get('year', today.year))
        selected_month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        selected_year = today.year
        selected_month = today.month

    purchases = DailyPurchase.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).select_related(
        'created_by',
        'approved_by'
    ).order_by('-date', '-created_at')

    # 🔥 GROUP THEO NGÀY + TÍNH TỔNG CHI
    purchase_map = {}

    for p in purchases:
        purchase_map.setdefault(p.date, []).append(p)

    purchase_days = []

    for d, items in purchase_map.items():
        total_cost = sum(i.actual_cost for i in items)

        purchase_days.append({
            'date': d,
            'items': items,
            'total_cost': total_cost
        })

    purchase_days = sorted(purchase_days, key=lambda x: x['date'], reverse=True)

    return render(request, 'finance/purchase_list.html', {
        'purchase_days': purchase_days,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'month_choices': range(1, 13),
        'year_choices': range(today.year - 2, today.year + 3),
    })


# =========================
# CREATE
# =========================
@login_required
@user_passes_test(can_manage_purchase)
def purchase_create(request):
    if request.method == 'POST':
        form = DailyPurchaseForm(request.POST, request.FILES)

        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.created_by = request.user

            # trạng thái
            if is_admin(request.user):
                purchase.status = DailyPurchase.STATUS_APPROVED
            else:
                purchase.status = DailyPurchase.STATUS_PENDING

            purchase.save()

            # =========================
            # 🔥 LƯU NGUYÊN LIỆU BỔ SUNG
            # =========================
            if purchase.purchase_type == 'extra':
                names = request.POST.getlist('extra_name[]')
                quantities = request.POST.getlist('extra_quantity[]')
                units = request.POST.getlist('extra_unit[]')

                for i in range(len(names)):
                    if names[i]:
                        PurchaseExtraItem.objects.create(
                            purchase=purchase,
                            ingredient_name=names[i],
                            quantity=quantities[i] or 0,
                            unit=units[i]
                        )

            return redirect('purchase_list')
    else:
        form = DailyPurchaseForm(initial={
            'date': date.today()
        })

    return render(request, 'finance/purchase_form.html', {
        'form': form,
        'page_title': 'Nhập chi phí thực tế',
        'submit_label': 'Lưu chi phí',
        'is_create': True,
    })


# =========================
# UPDATE
# =========================
@login_required
@user_passes_test(can_manage_purchase)
def purchase_update(request, pk):
    purchase = get_object_or_404(DailyPurchase, pk=pk)

    if purchase.status == DailyPurchase.STATUS_APPROVED and not is_admin(request.user):
        messages.error(request, "Chi phí đã được duyệt, không thể chỉnh sửa.")
        return redirect('purchase_list')

    if request.method == 'POST':
        form = DailyPurchaseForm(request.POST, request.FILES, instance=purchase)

        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.created_by = request.user

            if is_admin(request.user):
                purchase.status = DailyPurchase.STATUS_APPROVED
            else:
                purchase.status = DailyPurchase.STATUS_PENDING

            purchase.save()

            # 🔥 clear + save lại extra items
            purchase.extra_items.all().delete()

            if purchase.purchase_type == 'extra':
                names = request.POST.getlist('extra_name[]')
                quantities = request.POST.getlist('extra_quantity[]')
                units = request.POST.getlist('extra_unit[]')

                for i in range(len(names)):
                    if names[i]:
                        PurchaseExtraItem.objects.create(
                            purchase=purchase,
                            ingredient_name=names[i],
                            quantity=quantities[i] or 0,
                            unit=units[i]
                        )

            return redirect('purchase_list')
    else:
        form = DailyPurchaseForm(instance=purchase)

    return render(request, 'finance/purchase_form.html', {
        'form': form,
        'page_title': 'Cập nhật chi phí',
        'submit_label': 'Cập nhật',
        'is_create': False,
    })


# =========================
# AJAX: INGREDIENTS
# =========================
@login_required
@user_passes_test(can_manage_purchase)
def purchase_ingredients_by_date(request):
    date_str = request.GET.get('date')

    try:
        target_date = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return JsonResponse({
            'success': False,
            'message': 'Ngày không hợp lệ.',
            'ingredients': [],
        })

    menu = DailyMenu.objects.filter(
        date=target_date,
        status=DailyMenu.STATUS_APPROVED
    ).prefetch_related(
        'items__dish__ingredients__ingredient'
    ).first()

    if not menu:
        return JsonResponse({
            'success': True,
            'has_menu': False,
            'ingredients': [],
        })

    registered_count = menu.registered_count
    ingredient_map = {}

    for menu_item in menu.items.all():
        for ing in menu_item.dish.ingredients.all():
            key = (ing.ingredient.name.lower(), ing.unit)

            if key not in ingredient_map:
                ingredient_map[key] = {
                    'name': ing.ingredient.name.capitalize(),
                    'unit': ing.unit,
                    'total_quantity': 0,
                }

            if registered_count:
                ingredient_map[key]['total_quantity'] += (
                    float(ing.quantity_per_person) * registered_count
                )

    return JsonResponse({
        'success': True,
        'has_menu': True,
        'ingredients': list(ingredient_map.values()),
    })