from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from decimal import Decimal, InvalidOperation
from datetime import date

from meals.models import DailyMenu
from .models import DailyPurchase, ExtraPurchaseRequest, ExtraPurchaseRequestItem, PurchaseEditLog, PurchaseExtraItem
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
    ).prefetch_related(
        'extra_items'
    ).order_by('-date', '-created_at')

    purchase_map = {}
    for p in purchases:
        purchase_map.setdefault(p.date, []).append(p)

    def expected_ingredients_for(target_date):
        """Nguyên liệu dự kiến của ngày — gộp từ thực đơn đã duyệt, tính 1 lần
        cho cả ngày (không lặp lại theo từng hóa đơn)."""
        menu = DailyMenu.objects.filter(
            date=target_date,
            status=DailyMenu.STATUS_APPROVED
        ).prefetch_related('items__dish__ingredients__ingredient').first()
        if not menu:
            return []
        registered_count = menu.registered_count or 0
        ingredient_map = {}
        for menu_item in menu.items.all():
            for ing in menu_item.dish.ingredients.all():
                key = (ing.ingredient.name, ing.unit)
                if key not in ingredient_map:
                    ingredient_map[key] = {
                        'name': ing.ingredient.name,
                        'unit': ing.unit,
                        'total_quantity': 0,
                    }
                ingredient_map[key]['total_quantity'] += (
                    float(ing.quantity_per_person) * registered_count
                )
        return list(ingredient_map.values())

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
            'expected_ingredients': expected_ingredients_for(d),
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
            # Parse danh sách items + phân loại TP/GV cho từng dòng.
            names = request.POST.getlist('ai_item_name[]')
            quantities = request.POST.getlist('ai_item_quantity[]')
            units = request.POST.getlist('ai_item_unit[]')
            prices = request.POST.getlist('ai_item_price[]')
            types = request.POST.getlist('ai_item_type[]')

            tp_items = []
            gv_items = []

            for i, raw_name in enumerate(names):
                name = (raw_name or '').strip()
                if not name:
                    continue

                try:
                    quantity = Decimal(
                        (quantities[i] if i < len(quantities) else '0').replace(',', '.')
                    )
                except (InvalidOperation, ValueError):
                    quantity = Decimal('0')

                unit = units[i] if i < len(units) else ''

                try:
                    price = Decimal(
                        (prices[i] if i < len(prices) else '0')
                        .replace('.', '').replace(',', '')
                    )
                except (InvalidOperation, ValueError):
                    price = Decimal('0')

                item_type = types[i] if i < len(types) else DailyPurchase.PURCHASE_TYPE_MAIN
                target = gv_items if item_type == DailyPurchase.PURCHASE_TYPE_EXTRA else tp_items
                target.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit,
                    'unit_price': price,
                    'line_total': quantity * price,
                })

            with transaction.atomic():
                if tp_items and gv_items:
                    # Có cả 2 loại → tạo 2 phiếu, share ảnh hóa đơn.
                    purchase_tp = form.save(commit=False)
                    purchase_tp.created_by = request.user
                    purchase_tp.status = DailyPurchase.STATUS_PENDING
                    purchase_tp.purchase_type = DailyPurchase.PURCHASE_TYPE_MAIN
                    purchase_tp.actual_cost = int(sum(it['line_total'] for it in tp_items))
                    purchase_tp.approved_by = None
                    purchase_tp.approved_at = None
                    purchase_tp.reject_reason = ''
                    purchase_tp.rejected_by = None
                    purchase_tp.rejected_at = None
                    purchase_tp.save()

                    for it in tp_items:
                        PurchaseExtraItem.objects.create(
                            purchase=purchase_tp,
                            date=purchase_tp.date,
                            ingredient_name=it['name'],
                            quantity=it['quantity'],
                            unit=it['unit'],
                            unit_price=it['unit_price'],
                        )

                    # Phiếu GV: copy data + copy file ảnh ra file thứ 2 trên disk
                    # (upload_to sẽ tự gen path khác vì purchase_type='extra').
                    purchase_gv = DailyPurchase(
                        date=purchase_tp.date,
                        purchase_type=DailyPurchase.PURCHASE_TYPE_EXTRA,
                        actual_cost=int(sum(it['line_total'] for it in gv_items)),
                        note=purchase_tp.note,
                        status=DailyPurchase.STATUS_PENDING,
                        created_by=request.user,
                    )

                    if purchase_tp.bill_image:
                        purchase_tp.bill_image.open('rb')
                        content = purchase_tp.bill_image.read()
                        purchase_tp.bill_image.close()
                        ext = purchase_tp.bill_image.name.rsplit('.', 1)[-1] or 'jpg'
                        purchase_gv.bill_image.save(
                            f'split.{ext}', ContentFile(content), save=False
                        )

                    purchase_gv.save()

                    for it in gv_items:
                        PurchaseExtraItem.objects.create(
                            purchase=purchase_gv,
                            date=purchase_gv.date,
                            ingredient_name=it['name'],
                            quantity=it['quantity'],
                            unit=it['unit'],
                            unit_price=it['unit_price'],
                        )

                    messages.success(
                        request,
                        'Đã tạo 2 phiếu chi phí (Thực phẩm + Gia vị).'
                    )
                else:
                    # Chỉ 1 loại (hoặc không có items) → 1 phiếu như cũ.
                    purchase = form.save(commit=False)
                    purchase.created_by = request.user
                    purchase.status = DailyPurchase.STATUS_PENDING
                    purchase.approved_by = None
                    purchase.approved_at = None
                    purchase.reject_reason = ''
                    purchase.rejected_by = None
                    purchase.rejected_at = None

                    if tp_items:
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_MAIN
                        purchase.actual_cost = int(sum(it['line_total'] for it in tp_items))
                    elif gv_items:
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_EXTRA
                        purchase.actual_cost = int(sum(it['line_total'] for it in gv_items))
                    # else: không có items, giữ purchase_type & actual_cost từ form.

                    purchase.save()

                    items_to_save = tp_items or gv_items
                    for it in items_to_save:
                        PurchaseExtraItem.objects.create(
                            purchase=purchase,
                            date=purchase.date,
                            ingredient_name=it['name'],
                            quantity=it['quantity'],
                            unit=it['unit'],
                            unit_price=it['unit_price'],
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

    was_previously_approved = (purchase.status == DailyPurchase.STATUS_APPROVED)

    if request.method == 'POST':
        form = DailyPurchaseForm(request.POST, request.FILES, instance=purchase)

        edit_reason = (request.POST.get('edit_reason') or '').strip()
        if was_previously_approved and not edit_reason:
            messages.error(request, 'Bạn phải nhập lý do chỉnh sửa chi phí đã được duyệt.')
            return render(request, 'finance/purchase_form.html', {
                'form': form,
                'page_title': 'Cập nhật chi phí',
                'submit_label': 'Cập nhật',
                'is_create': False,
                'was_previously_approved': was_previously_approved,
                'edit_reason_value': edit_reason,
            })

        if form.is_valid():
            previous_status = purchase.status
            old_type = purchase.purchase_type

            # Parse danh sách items + phân loại TP/GV cho từng dòng.
            names = request.POST.getlist('ai_item_name[]')
            quantities = request.POST.getlist('ai_item_quantity[]')
            units = request.POST.getlist('ai_item_unit[]')
            prices = request.POST.getlist('ai_item_price[]')
            types = request.POST.getlist('ai_item_type[]')

            tp_items = []
            gv_items = []
            for i, raw_name in enumerate(names):
                name = (raw_name or '').strip()
                if not name:
                    continue

                try:
                    quantity = Decimal(
                        (quantities[i] if i < len(quantities) else '0').replace(',', '.')
                    )
                except (InvalidOperation, ValueError):
                    quantity = Decimal('0')

                unit = units[i] if i < len(units) else ''

                try:
                    price = Decimal(
                        (prices[i] if i < len(prices) else '0')
                        .replace('.', '').replace(',', '')
                    )
                except (InvalidOperation, ValueError):
                    price = Decimal('0')

                item_type = types[i] if i < len(types) else DailyPurchase.PURCHASE_TYPE_MAIN
                target = gv_items if item_type == DailyPurchase.PURCHASE_TYPE_EXTRA else tp_items
                target.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit,
                    'unit_price': price,
                    'line_total': quantity * price,
                })

            split = bool(tp_items and gv_items)

            with transaction.atomic():
                purchase = form.save(commit=False)
                purchase.created_by = request.user
                purchase.status = DailyPurchase.STATUS_PENDING
                purchase.approved_by = None
                purchase.approved_at = None
                purchase.reject_reason = ''
                purchase.rejected_by = None
                purchase.rejected_at = None
                if was_previously_approved:
                    purchase.was_edited_after_approval = True

                if split:
                    # Có cả 2 loại → phiếu hiện tại giữ nhóm trùng loại cũ,
                    # tách nhóm còn lại ra phiếu mới (chờ duyệt lại).
                    if old_type == DailyPurchase.PURCHASE_TYPE_EXTRA:
                        keep_items, new_items = gv_items, tp_items
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_EXTRA
                        new_type = DailyPurchase.PURCHASE_TYPE_MAIN
                    else:
                        keep_items, new_items = tp_items, gv_items
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_MAIN
                        new_type = DailyPurchase.PURCHASE_TYPE_EXTRA
                    purchase.actual_cost = int(sum(it['line_total'] for it in keep_items))
                else:
                    keep_items = tp_items or gv_items
                    if tp_items:
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_MAIN
                        purchase.actual_cost = int(sum(it['line_total'] for it in tp_items))
                    elif gv_items:
                        purchase.purchase_type = DailyPurchase.PURCHASE_TYPE_EXTRA
                        purchase.actual_cost = int(sum(it['line_total'] for it in gv_items))
                    # else: không có items, giữ purchase_type & actual_cost từ form.

                purchase.save()

                # Recreate items của phiếu hiện tại.
                purchase.extra_items.all().delete()
                for it in keep_items:
                    PurchaseExtraItem.objects.create(
                        purchase=purchase,
                        date=purchase.date,
                        ingredient_name=it['name'],
                        quantity=it['quantity'],
                        unit=it['unit'],
                        unit_price=it['unit_price'],
                    )

                if split:
                    # Phiếu mới cho nhóm tách ra — copy ảnh hóa đơn.
                    new_purchase = DailyPurchase(
                        date=purchase.date,
                        purchase_type=new_type,
                        actual_cost=int(sum(it['line_total'] for it in new_items)),
                        note=purchase.note,
                        status=DailyPurchase.STATUS_PENDING,
                        created_by=request.user,
                    )
                    if purchase.bill_image:
                        purchase.bill_image.open('rb')
                        content = purchase.bill_image.read()
                        purchase.bill_image.close()
                        ext = purchase.bill_image.name.rsplit('.', 1)[-1] or 'jpg'
                        new_purchase.bill_image.save(
                            f'split.{ext}', ContentFile(content), save=False
                        )
                    new_purchase.save()
                    for it in new_items:
                        PurchaseExtraItem.objects.create(
                            purchase=new_purchase,
                            date=new_purchase.date,
                            ingredient_name=it['name'],
                            quantity=it['quantity'],
                            unit=it['unit'],
                            unit_price=it['unit_price'],
                        )

                if was_previously_approved:
                    PurchaseEditLog.objects.create(
                        purchase=purchase,
                        edited_by=request.user,
                        previous_status=previous_status,
                        reason=edit_reason,
                    )

            if split:
                messages.success(
                    request,
                    'Đã cập nhật và tách thành 2 phiếu (Thực phẩm + Gia vị), chờ duyệt lại.'
                )
            else:
                messages.success(request, 'Đã cập nhật chi phí, đang chờ phê duyệt lại.')
            return redirect('purchase_list')
    else:
        form = DailyPurchaseForm(instance=purchase)

    return render(request, 'finance/purchase_form.html', {
        'form': form,
        'page_title': 'Cập nhật chi phí',
        'submit_label': 'Cập nhật',
        'is_create': False,
        'was_previously_approved': was_previously_approved,
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