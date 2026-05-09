from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal, InvalidOperation
from datetime import date

from meals.models import DailyMenu
from .models import DailyPurchase, ExtraPurchaseRequest, PurchaseExtraItem
from accounts.permissions import is_admin, is_kitchen
from .forms import DailyPurchaseForm
from core.services.finance_ai import scan_receipt_image

def can_manage_purchase(user):
    return is_admin(user) or is_kitchen(user)

@login_required
@user_passes_test(can_manage_purchase)
def scan_bill_ajax(request):
    if request.method == 'POST' and request.FILES.get('bill_image'):
        bill_file = request.FILES['bill_image']
        file_bytes = bill_file.read()
        mime_type = bill_file.content_type
        
        result = scan_receipt_image(file_bytes, mime_type)
        return JsonResponse(result)
        
    return JsonResponse({'error': 'Yêu cầu không hợp lệ.'}, status=400)



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
        'approved_by',
        'extra_request',
    ).prefetch_related(
        'extra_request__items',
        'extra_items'
    ).order_by('-date', '-created_at')

    purchase_map = {}
    
    for p in purchases:
        if p.purchase_type == DailyPurchase.PURCHASE_TYPE_MAIN:
            menu = DailyMenu.objects.filter(
                date=p.date,
                status=DailyMenu.STATUS_APPROVED
            ).prefetch_related(
                'items__dish__ingredients__ingredient'
            ).first()

            ingredient_map = {}

            if menu:
                registered_count = menu.registered_count or 0

                for menu_item in menu.items.all():
                    for ing in menu_item.dish.ingredients.all():
                        key = (ing.ingredient.name, ing.unit)

                        if key not in ingredient_map:
                            ingredient_map[key] = {
                                'name': ing.ingredient.name,
                                'unit': ing.unit,
                                'quantity': 0,
                                'total_quantity': 0,
                            }

                        q = float(ing.quantity_per_person)
                        ingredient_map[key]['quantity'] += q
                        ingredient_map[key]['total_quantity'] += q * registered_count

            p.main_ingredients = list(ingredient_map.values())

        else:
            p.main_ingredients = []

            if p.extra_request:
                p.approved_extra_items = list(p.extra_request.items.all())
            else:
                p.approved_extra_items = []

        purchase_map.setdefault(p.date, []).append(p)

    purchase_days = []

    for d, items in purchase_map.items():
        total_cost = sum(
            item.actual_cost
            for item in items
            if item.status == DailyPurchase.STATUS_APPROVED
        )

        purchase_days.append({
            'date': d,
            'items': items,
            'total_cost': total_cost,
            'count': len(items),
        })

    purchase_days = sorted(
        purchase_days,
        key=lambda x: x['date'],
        reverse=True
    )

    return render(request, 'finance/purchase_list.html', {
        'purchase_days': purchase_days,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'month_choices': range(1, 13),
        'year_choices': range(today.year - 2, today.year + 3),
    })


@login_required
@user_passes_test(can_manage_purchase)
def purchase_create(request):
    if request.method == 'POST':
        form = DailyPurchaseForm(request.POST, request.FILES)

        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.created_by = request.user
            purchase.status = DailyPurchase.STATUS_PENDING
            purchase.approved_by = None
            purchase.approved_at = None
            purchase.reject_reason = ''
            purchase.rejected_by = None
            purchase.rejected_at = None
            purchase.save()

            # Process dynamic items
            names = request.POST.getlist('ai_item_name[]')
            quantities = request.POST.getlist('ai_item_quantity[]')
            units = request.POST.getlist('ai_item_unit[]')
            prices = request.POST.getlist('ai_item_price[]')

            for i, raw_name in enumerate(names):
                name = (raw_name or '').strip()
                if not name: continue
                
                try: quantity = Decimal(quantities[i].replace(',', '.'))
                except: quantity = Decimal('0')
                
                unit = units[i] if i < len(units) else ''
                
                try: price = Decimal(prices[i].replace(',', '.'))
                except: price = Decimal('0')

                PurchaseExtraItem.objects.create(
                    purchase=purchase,
                    date=purchase.date,
                    ingredient_name=name,
                    quantity=quantity,
                    unit=unit,
                    unit_price=price
                )

            messages.success(request, 'Đã gửi chi phí, đang chờ phê duyệt.')
            return redirect('purchase_list')
    else:
        form = DailyPurchaseForm(initial={
            'date': date.today()
        })

    return render(request, 'finance/purchase_form.html', {
        'form': form,
        'page_title': 'Nhập chi phí thực tế',
        'submit_label': 'Gửi phê duyệt',
        'is_create': True,
    })


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
            purchase.status = DailyPurchase.STATUS_PENDING
            purchase.approved_by = None
            purchase.approved_at = None
            purchase.reject_reason = ''
            purchase.rejected_by = None
            purchase.rejected_at = None
            purchase.save()
            
            # Update dynamic items: delete old ones, recreate new ones
            purchase.extra_items.all().delete()
            
            names = request.POST.getlist('ai_item_name[]')
            quantities = request.POST.getlist('ai_item_quantity[]')
            units = request.POST.getlist('ai_item_unit[]')
            prices = request.POST.getlist('ai_item_price[]')

            for i, raw_name in enumerate(names):
                name = (raw_name or '').strip()
                if not name: continue
                
                try: quantity = Decimal(quantities[i].replace(',', '.'))
                except: quantity = Decimal('0')
                
                unit = units[i] if i < len(units) else ''
                
                try: price = Decimal(prices[i].replace(',', '.'))
                except: price = Decimal('0')

                PurchaseExtraItem.objects.create(
                    purchase=purchase,
                    date=purchase.date,
                    ingredient_name=name,
                    quantity=quantity,
                    unit=unit,
                    unit_price=price
                )

            messages.success(request, 'Đã cập nhật chi phí, đang chờ phê duyệt lại.')
            return redirect('purchase_list')
    else:
        form = DailyPurchaseForm(instance=purchase)

    return render(request, 'finance/purchase_form.html', {
        'form': form,
        'page_title': 'Cập nhật chi phí',
        'submit_label': 'Cập nhật',
        'is_create': False,
    })


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
            'has_menu': False,
            'registered_count': None,
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
            'message': 'Ngày này chưa có thực đơn đã duyệt.',
            'registered_count': None,
            'ingredients': [],
        })

    registered_count = menu.registered_count or 0
    ingredient_map = {}

    for menu_item in menu.items.all():
        for ing in menu_item.dish.ingredients.all():
            key = (ing.ingredient.name.lower(), ing.unit)
            quantity_per_person = float(ing.quantity_per_person)

            if key not in ingredient_map:
                ingredient_map[key] = {
                    'name': ing.ingredient.name.capitalize(),
                    'unit': ing.unit,
                    'quantity_per_person': 0,
                    'total_quantity': 0,
                }

            ingredient_map[key]['quantity_per_person'] += quantity_per_person
            ingredient_map[key]['total_quantity'] += quantity_per_person * registered_count

    return JsonResponse({
        'success': True,
        'has_menu': True,
        'registered_count': registered_count,
        'ingredients': list(ingredient_map.values()),
    })


@login_required
@user_passes_test(can_manage_purchase)
def extra_request_by_date(request):
    date_str = request.GET.get('date')

    try:
        target_date = date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return JsonResponse({
            'success': False,
            'message': 'Ngày không hợp lệ.',
            'requests': [],
        })

    used_request_ids = DailyPurchase.objects.filter(
        purchase_type=DailyPurchase.PURCHASE_TYPE_EXTRA,
        extra_request__isnull=False,
        status__in=[
            DailyPurchase.STATUS_PENDING,
            DailyPurchase.STATUS_APPROVED,
        ]
    ).values_list('extra_request_id', flat=True)

    requests = ExtraPurchaseRequest.objects.filter(
        date=target_date,
        status=ExtraPurchaseRequest.STATUS_APPROVED,
    ).exclude(
        id__in=used_request_ids
    ).select_related(
        'created_by'
    ).prefetch_related(
        'items'
    ).order_by('created_at')

    data = []

    for req in requests:
        data.append({
            'id': req.id,
            'date': req.date.strftime('%d/%m/%Y'),
            'created_by': req.created_by.username if req.created_by else '-',
            'note': req.note or '',
            'items': [
                {
                    'name': item.ingredient_name,
                    'quantity': float(item.quantity),
                    'unit': item.unit,
                    'unit_price': float(item.unit_price or 0),
                }
                for item in req.items.all()
            ]
        })

    return JsonResponse({
        'success': True,
        'requests': data,
    })


@login_required
def extra_request_create(request):
    if request.method == 'POST':
        date_val = request.POST.get('date')
        note = request.POST.get('note', '').strip()

        if not date_val:
            messages.error(request, 'Bạn phải chọn ngày áp dụng.')
            return redirect('extra_request_create')

        req = ExtraPurchaseRequest.objects.create(
            date=date_val,
            note=note,
            created_by=request.user,
            status=ExtraPurchaseRequest.STATUS_PENDING
        )

        names = request.POST.getlist('extra_name[]')
        quantities = request.POST.getlist('extra_quantity[]')
        units = request.POST.getlist('extra_unit[]')
        unit_prices = request.POST.getlist('extra_unit_price[]')

        has_item = False

        for i, raw_name in enumerate(names):
            name = (raw_name or '').strip()

            if not name:
                continue

            quantity = quantities[i] if i < len(quantities) else 0
            unit = units[i] if i < len(units) else ''
            unit_price = unit_prices[i] if i < len(unit_prices) else 0

            ExtraPurchaseRequestItem.objects.create(
                request=req,
                ingredient_name=name,
                quantity=quantity or 0,
                unit=unit or '',
                unit_price=unit_price or 0,
            )

            has_item = True

        if not has_item:
            req.delete()
            messages.error(request, 'Bạn phải nhập ít nhất 1 nguyên liệu bổ sung.')
            return redirect('extra_request_create')

        messages.success(request, 'Đã tạo đơn mua bổ sung, đang chờ admin phê duyệt.')
        return redirect('extra_request_list')

    return render(request, 'finance/extra_request_form.html', {
        'page_title': 'Đơn mua bổ sung',
        'default_date': date.today(),
    })



def format_qty(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    if d == d.to_integral():
        return str(int(d))

    return str(d.normalize()).replace('.', ',')


def format_main_qty(value, unit):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value, unit

    if str(unit).lower() == 'g' and d > 1000:
        return format_qty(d / Decimal('1000')), 'kg'

    return format_qty(d), unit


@login_required
def extra_request_list(request):
    today = date.today()

    date_str = request.GET.get('date')
    order_type = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    try:
        selected_date = date.fromisoformat(date_str) if date_str else today
    except (TypeError, ValueError):
        selected_date = today

    main_order = None

    if order_type in ['', 'main']:
        menu = DailyMenu.objects.filter(
            date=selected_date
        ).prefetch_related(
            'items__dish__ingredients__ingredient'
        ).order_by('-created_at').first()

        if menu:
            main_purchase = DailyPurchase.objects.filter(
                date=selected_date,
                purchase_type=DailyPurchase.PURCHASE_TYPE_MAIN
            ).exclude(
                status=DailyPurchase.STATUS_REJECTED
            ).first()

            show_main = True

            if status_filter in ['pending', 'approved', 'rejected']:
                show_main = menu.status == status_filter

            if status_filter == 'cost_entered':
                show_main = main_purchase is not None

            if status_filter == 'cost_not_entered':
                show_main = main_purchase is None

            if show_main:
                registered_count = menu.registered_count or 0
                ingredient_map = {}

                for menu_item in menu.items.all():
                    for ing in menu_item.dish.ingredients.all():
                        key = (ing.ingredient.name, ing.unit)

                        if key not in ingredient_map:
                            ingredient_map[key] = {
                                'name': ing.ingredient.name,
                                'unit': ing.unit,
                                'quantity': Decimal('0'),
                                'total_quantity': Decimal('0'),
                            }

                        q = Decimal(str(ing.quantity_per_person))
                        ingredient_map[key]['quantity'] += q
                        ingredient_map[key]['total_quantity'] += q * registered_count

                ingredients = []

                for row in ingredient_map.values():
                    q_display, q_unit = format_main_qty(row['quantity'], row['unit'])
                    total_display, total_unit = format_main_qty(row['total_quantity'], row['unit'])

                    ingredients.append({
                        'name': row['name'],
                        'quantity_display': q_display,
                        'quantity_unit': q_unit,
                        'total_display': total_display,
                        'total_unit': total_unit,
                    })

                main_order = {
                    'id': menu.id,
                    'date': menu.date,
                    'status': menu.status,
                    'status_display': menu.get_status_display(),
                    'created_by': menu.created_by,
                    'approved_by': getattr(menu, 'approved_by', None),
                    'has_purchase': main_purchase is not None,
                    'registered_count': registered_count,
                    'ingredients': ingredients,
                }

    extra_requests = ExtraPurchaseRequest.objects.filter(
        date=selected_date
    ).select_related(
        'created_by',
        'approved_by'
    ).prefetch_related(
        'items',
        'purchases'
    ).order_by('-created_at')

    if order_type == 'main':
        extra_requests = ExtraPurchaseRequest.objects.none()

    if order_type == 'extra':
        main_order = None

    if status_filter in ['pending', 'approved', 'rejected']:
        extra_requests = extra_requests.filter(status=status_filter)

    extra_request_list_data = []

    for req in extra_requests:
        has_purchase = req.purchases.exclude(
            status=DailyPurchase.STATUS_REJECTED
        ).exists()

        if status_filter == 'cost_entered' and not has_purchase:
            continue

        if status_filter == 'cost_not_entered' and has_purchase:
            continue

        req.has_purchase = has_purchase
        extra_request_list_data.append(req)

    total_orders = len(extra_request_list_data) + (1 if main_order else 0)

    approved_count = 0
    pending_count = 0
    cost_entered_count = 0

    if main_order:
        if main_order['status'] == DailyMenu.STATUS_APPROVED:
            approved_count += 1
        elif main_order['status'] == DailyMenu.STATUS_PENDING:
            pending_count += 1

        if main_order['has_purchase']:
            cost_entered_count += 1

    for req in extra_request_list_data:
        if req.status == ExtraPurchaseRequest.STATUS_APPROVED:
            approved_count += 1
        elif req.status == ExtraPurchaseRequest.STATUS_PENDING:
            pending_count += 1

        if req.has_purchase:
            cost_entered_count += 1

    return render(request, 'finance/extra_request_list.html', {
        'selected_date': selected_date,
        'order_type': order_type,
        'status_filter': status_filter,
        'main_order': main_order,
        'requests': extra_request_list_data,
        'total_orders': total_orders,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'cost_entered_count': cost_entered_count,
    })