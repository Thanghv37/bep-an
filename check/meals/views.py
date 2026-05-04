#meals/views
import calendar
from datetime import datetime, date, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime
from django.contrib import messages
from .models import (
    Dish,
    DailyMenu,
    DailyMenuItem,
    Ingredient,
    DishIngredient,
    MenuRejectLog,
    DishRejectLog,
)
from .forms import DishForm, DailyMenuForm
from finance.models import DailyPurchase, PurchaseRejectLog
from accounts.permissions import (
    is_admin,
    can_manage_dish,
    can_manage_menu,
    can_manage_approval,
)



def staff_required(user):
    return user.is_staff or user.is_superuser


def get_grouped_dishes():
    return {
        'main': Dish.objects.filter(is_active=True, status=Dish.STATUS_APPROVED, dish_type='main').order_by('name'),
        'side': Dish.objects.filter(is_active=True, status=Dish.STATUS_APPROVED, dish_type='side').order_by('name'),
        'soup': Dish.objects.filter(is_active=True, status=Dish.STATUS_APPROVED, dish_type='soup').order_by('name'),
        'dessert': Dish.objects.filter(is_active=True, status=Dish.STATUS_APPROVED, dish_type='dessert').order_by('name'),
    }




def is_late_menu_date(target_date, now=None):
    if now is None:
        now = timezone.localtime()

    today = now.date()

    if target_date < today:
        return True

    if target_date == today and now.time() >= time(11, 0):
        return True

    return False


def can_delete_menu(menu_date, now=None):
    return not is_late_menu_date(menu_date, now=now)


@login_required
@user_passes_test(can_manage_dish)
def dish_list(request):
    keyword = request.GET.get('q', '').strip()
    dish_type = request.GET.get('type', '').strip()

    dishes = Dish.objects.all().order_by('name')

    if keyword:
        dishes = dishes.filter(name__icontains=keyword)

    if dish_type:
        dishes = dishes.filter(dish_type=dish_type)

    context = {
        'dishes': dishes,
        'keyword': keyword,
        'dish_type': dish_type,
        'dish_type_choices': Dish.DISH_TYPE_CHOICES,
    }
    return render(request, 'meals/dish_list.html', context)


def save_dish_ingredients_from_post(dish, post_data):
    ingredient_names = post_data.getlist('ingredient_name[]')
    quantities = post_data.getlist('quantity_per_person[]')
    units = post_data.getlist('unit[]')

    DishIngredient.objects.filter(dish=dish).delete()

    has_valid_ingredient = False

    for name, quantity, unit in zip(ingredient_names, quantities, units):
        name = (name or '').strip()
        quantity = (quantity or '').strip()
        unit = (unit or '').strip()

        if not name and not quantity:
            continue

        if not name or not quantity or not unit:
            raise ValueError('Bạn phải nhập đầy đủ tên nguyên liệu, khẩu phần và đơn vị.')

        normalized_name = name.lower()

        ingredient = Ingredient.objects.filter(name__iexact=normalized_name).first()

        if not ingredient:
            ingredient = Ingredient.objects.create(
                name=normalized_name,
                default_unit=unit
            )

        DishIngredient.objects.create(
            dish=dish,
            ingredient=ingredient,
            quantity_per_person=quantity,
            unit=unit,
        )

        has_valid_ingredient = True

    if not has_valid_ingredient:
        raise ValueError('Bạn phải nhập ít nhất 1 nguyên liệu cho món ăn.')


@login_required
@user_passes_test(can_manage_dish)
def dish_create(request):
    ingredients = Ingredient.objects.all().order_by('name')

    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                dish = form.save(commit=False)
                dish.portion_per_person = 0
                dish.portion_unit = 'g'

                if is_admin(request.user):
                    dish.status = Dish.STATUS_APPROVED
                    dish.approved_by = request.user
                    dish.approved_at = timezone.localtime()
                else:
                    dish.status = Dish.STATUS_PENDING
                    dish.approved_by = None
                    dish.approved_at = None
                    dish.reject_reason = ''
                    dish.rejected_by = None
                    dish.rejected_at = None

                dish.save()
                save_dish_ingredients_from_post(dish, request.POST)

                messages.success(request, 'Đã thêm món ăn mới.')
                return redirect('dish_list')
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = DishForm()

    return render(request, 'meals/dish_form.html', {
        'form': form,
        'page_title': 'Thêm món ăn',
        'submit_label': 'Lưu món ăn',
        'ingredients': ingredients,
        'dish_ingredients': [],
    })


@login_required
@user_passes_test(can_manage_dish)
def dish_update(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    ingredients = Ingredient.objects.all().order_by('name')

    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        if form.is_valid():
            try:
                dish = form.save(commit=False)
                dish.portion_per_person = 0
                dish.portion_unit = 'g'

                if is_admin(request.user):
                    dish.status = Dish.STATUS_APPROVED
                    dish.approved_by = request.user
                    dish.approved_at = timezone.localtime()
                else:
                    dish.status = Dish.STATUS_PENDING
                    dish.approved_by = None
                    dish.approved_at = None
                    dish.reject_reason = ''
                    dish.rejected_by = None
                    dish.rejected_at = None

                dish.save()
                save_dish_ingredients_from_post(dish, request.POST)

                messages.success(request, f'Đã cập nhật món "{dish.name}".')
                return redirect('dish_list')
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = DishForm(instance=dish)

    return render(request, 'meals/dish_form.html', {
        'form': form,
        'page_title': 'Cập nhật món ăn',
        'submit_label': 'Cập nhật',
        'ingredients': ingredients,
        'dish_ingredients': dish.ingredients.select_related('ingredient').all(),
    })

@login_required
@user_passes_test(can_manage_dish)
def dish_delete(request, pk):
    dish = get_object_or_404(Dish, pk=pk)

    # 🔥 CHẶN NHÂN VIÊN XÓA MÓN ĐÃ DUYỆT
    if dish.status == Dish.STATUS_APPROVED and not is_admin(request.user):
        messages.error(request, "Món đã được duyệt, nhân viên bếp không thể xóa.")
        return redirect('dish_list')

    dish.delete()
    messages.success(request, "Đã xóa món ăn.")
    return redirect('dish_list')


@login_required
@user_passes_test(can_manage_menu)
def menu_list(request):
    selected_dates_raw = request.GET.get('dates', '').strip()
    focus_date_raw = request.GET.get('focus_date', '').strip()

    selected_dates = []
    menus = []

    if selected_dates_raw:
        for part in selected_dates_raw.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                selected_dates.append(datetime.strptime(part, '%Y-%m-%d').date())
            except ValueError:
                continue

    selected_dates = sorted(selected_dates)

    now = timezone.localtime()
    today = now.date()

    if selected_dates:
        selected_menus = DailyMenu.objects.filter(
            date__in=selected_dates
        ).prefetch_related('items__dish')
        selected_menu_map = {menu.date: menu for menu in selected_menus}

        for d in selected_dates:
            menu = selected_menu_map.get(d)
            menus.append({
                'date': d,
                'menu': menu,
                'can_delete': can_delete_menu(d, now=now) if menu else False,
                'is_late_menu': bool(menu and menu.edit_reason),
            })

    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year = today.year
        month = today.month

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(year, month)

    month_menu_queryset = DailyMenu.objects.filter(
        date__year=year,
        date__month=month
    )
    month_menu_map = {menu.date: menu for menu in month_menu_queryset}

    calendar_weeks = []
    for week in month_days:
        week_data = []
        for day in week:
            menu = month_menu_map.get(day)

            week_data.append({
                'date': day,
                'date_str': day.strftime('%Y-%m-%d'),
                'is_current_month': day.month == month,
                'has_menu': menu is not None,
                'is_today': day == today,
                'menu_id': menu.id if menu else None,
                'is_late_menu': bool(menu and menu.edit_reason),
                'status': menu.status if menu else None,
                'status_display': menu.get_status_display() if menu else None,
            })
        calendar_weeks.append(week_data)

    focus_date = None
    focus_menu = None
    preparation_items = []

    if focus_date_raw:
        try:
            focus_date = datetime.strptime(focus_date_raw, '%Y-%m-%d').date()
        except ValueError:
            focus_date = None
    elif selected_dates:
        focus_date = selected_dates[0]

    focus_registered_count = None
    focus_can_delete = False

    if focus_date:
        focus_menu = DailyMenu.objects.filter(
            date=focus_date
        ).prefetch_related('items__dish').first()

        focus_registered_count = get_registered_count(focus_date)
        focus_can_delete = can_delete_menu(focus_date, now=now) if focus_menu else False

        if focus_menu:
            ingredient_summary = {}

            for menu_item in focus_menu.items.prefetch_related('dish__ingredients__ingredient').all():
                dish = menu_item.dish

                for dish_ingredient in dish.ingredients.select_related('ingredient').all():
                    key = (
                        dish_ingredient.ingredient.name.strip().lower(),
                        dish_ingredient.unit
                    )

                    if key not in ingredient_summary:
                        ingredient_summary[key] = {
                            'ingredient_name': dish_ingredient.ingredient.name,
                            'unit': dish_ingredient.unit,
                            'quantity_per_person': 0,
                            'required_total_quantity': 0,
                            'dish_names': [],
                        }

                    ingredient_summary[key]['quantity_per_person'] += dish_ingredient.quantity_per_person

                    if focus_registered_count is not None:
                        ingredient_summary[key]['required_total_quantity'] += (
                            dish_ingredient.quantity_per_person * focus_registered_count
                        )

                    if dish.name not in ingredient_summary[key]['dish_names']:
                        ingredient_summary[key]['dish_names'].append(dish.name)

            preparation_items = list(ingredient_summary.values())

    context = {
        'selected_dates_input': ', '.join([d.strftime('%Y-%m-%d') for d in selected_dates]),
        'menus': menus,
        'calendar_weeks': calendar_weeks,
        'calendar_month': month,
        'calendar_year': year,
        'focus_date': focus_date,
        'focus_menu': focus_menu,
        'preparation_items': preparation_items,
        'focus_registered_count': focus_registered_count,
        'focus_can_delete': focus_can_delete,
        'selected_month': month,
        'selected_year': year,
        'month_choices': range(1, 13),
        'year_choices': range(today.year - 2, today.year + 3),
    }
    return render(request, 'meals/menu_list.html', context)


@login_required
@user_passes_test(can_manage_menu)
def menu_create(request):
    preselected_date = request.GET.get('date', '').strip()
    now = timezone.localtime()

    requires_reason = False
    initial_data = {}

    if preselected_date:
        initial_data['date'] = preselected_date
        try:
            parsed_date = datetime.strptime(preselected_date, '%Y-%m-%d').date()
            requires_reason = is_late_menu_date(parsed_date, now=now)
        except ValueError:
            pass

    if request.method == 'POST':
        form = DailyMenuForm(request.POST, user=request.user)
        if form.is_valid():
            selected_dishes = form.cleaned_data['dishes']
            menu_date = form.cleaned_data['date']
            edit_reason = form.cleaned_data.get('edit_reason', '').strip()

            requires_reason = is_late_menu_date(menu_date, now=now)

            if requires_reason and not edit_reason:
                form.add_error('edit_reason', 'Bạn phải nhập lý do chỉnh sửa cho trường hợp tạo menu trễ.')
            else:
                menu = DailyMenu.objects.filter(date=menu_date).first()
                if not menu:
                    menu = DailyMenu()

                menu.date = menu_date
                if is_admin(request.user):
                    menu.status = form.cleaned_data['status']
                else:
                    menu.status = DailyMenu.STATUS_PENDING

                # Khi gửi lại sau từ chối thì reset trạng thái từ chối hiện tại,
                # còn lịch sử cũ nằm trong MenuRejectLog.
                if menu.status == DailyMenu.STATUS_PENDING:
                    menu.reject_reason = ''
                    menu.rejected_by = None
                    menu.rejected_at = None

                menu.note = form.cleaned_data['note']
                menu.created_by = request.user
                menu.edit_reason = edit_reason if requires_reason else ''
                menu.last_edited_at = now
                menu.save()

                menu.items.all().delete()

                for index, dish in enumerate(selected_dishes, start=1):
                    DailyMenuItem.objects.create(
                        daily_menu=menu,
                        dish=dish,
                        sort_order=index
                    )

                messages.success(request, f'Đã tạo thực đơn ngày {menu.date.strftime("%d/%m/%Y")}.')
                return redirect('menu_list')
    else:
        form = DailyMenuForm(initial=initial_data, user=request.user)

    return render(request, 'meals/menu_form.html', {
        'form': form,
        'page_title': 'Lên thực đơn',
        'submit_label': 'Lưu thực đơn',
        'grouped_dishes': get_grouped_dishes(),
        'selected_dish_ids': [],
        'requires_reason': requires_reason,
    })


@login_required
@user_passes_test(can_manage_menu)
def menu_update(request, pk):
    menu = get_object_or_404(
        DailyMenu.objects.prefetch_related('items__dish'),
        pk=pk
    )

    now = timezone.localtime()
    requires_reason = is_late_menu_date(menu.date, now=now)

    initial_dishes = list(menu.items.values_list('dish_id', flat=True))

    if request.method == 'POST':
        post_data = request.POST.copy()

        if not is_admin(request.user):
            post_data['status'] = DailyMenu.STATUS_PENDING

        form = DailyMenuForm(post_data, instance=menu, user=request.user)
        if form.is_valid():
            selected_dishes = form.cleaned_data['dishes']
            edit_reason = form.cleaned_data.get('edit_reason', '').strip()
            menu_date = form.cleaned_data['date']

            requires_reason = is_late_menu_date(menu_date, now=now)

            if requires_reason and not edit_reason:
                form.add_error('edit_reason', 'Bạn phải nhập lý do chỉnh sửa cho trường hợp này.')
            else:
                menu.date = menu_date
                if is_admin(request.user):
                    menu.status = form.cleaned_data['status']
                else:
                    menu.status = DailyMenu.STATUS_PENDING

                # Khi gửi lại sau từ chối thì reset trạng thái từ chối hiện tại,
                # còn lịch sử cũ nằm trong MenuRejectLog.
                if menu.status == DailyMenu.STATUS_PENDING:
                    menu.reject_reason = ''
                    menu.rejected_by = None
                    menu.rejected_at = None

                menu.note = form.cleaned_data['note']
                menu.edit_reason = edit_reason if requires_reason else ''
                menu.last_edited_at = now
                menu.save()

                menu.items.all().delete()

                for index, dish in enumerate(selected_dishes, start=1):
                    DailyMenuItem.objects.create(
                        daily_menu=menu,
                        dish=dish,
                        sort_order=index
                    )

                messages.success(request, 'Đã cập nhật thực đơn.')
                return redirect('menu_list')
    else:
        form = DailyMenuForm(instance=menu, initial={'dishes': initial_dishes}, user=request.user)

    return render(request, 'meals/menu_form.html', {
        'form': form,
        'page_title': 'Cập nhật thực đơn',
        'submit_label': 'Cập nhật thực đơn',
        'grouped_dishes': get_grouped_dishes(),
        'selected_dish_ids': initial_dishes if request.method == 'GET' else request.POST.getlist('dishes'),
        'requires_reason': requires_reason,
    })


@login_required
@user_passes_test(can_manage_menu)
def menu_delete(request, pk):
    menu = get_object_or_404(DailyMenu, pk=pk)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('menu_list')

    now = timezone.localtime()

    if not can_delete_menu(menu.date, now=now):
        messages.error(
            request,
            f'Bữa ăn ngày {menu.date.strftime("%d/%m/%Y")} đã qua, không thể xóa !'
        )
        return redirect('menu_list')

    menu_date_str = menu.date.strftime("%d/%m/%Y")
    menu.delete()

    messages.success(request, f'Đã xóa thực đơn ngày {menu_date_str}.')
    return redirect('menu_list')


@login_required
@user_passes_test(can_manage_approval)
def approval_dashboard(request):
    pending_dishes = Dish.objects.filter(
        status=Dish.STATUS_PENDING
    ).prefetch_related(
        'ingredients__ingredient'
    ).order_by('-created_at')

    pending_menus = DailyMenu.objects.filter(
        status=DailyMenu.STATUS_PENDING
    ).prefetch_related('items__dish').order_by('date')

    pending_purchases = DailyPurchase.objects.filter(
        status=DailyPurchase.STATUS_PENDING
    ).select_related('created_by').order_by('-date')

    for purchase in pending_purchases:
        menu = DailyMenu.objects.filter(
            date=purchase.date,
            status=DailyMenu.STATUS_APPROVED
        ).prefetch_related(
            'items__dish__ingredients__ingredient'
        ).first()

        ingredient_map = {}

        if menu:
            registered_count = menu.registered_count
            purchase.registered_count = registered_count

            for menu_item in menu.items.all():
                for ing in menu_item.dish.ingredients.all():
                    key = (ing.ingredient.name.strip().lower(), ing.unit)

                    if key not in ingredient_map:
                        ingredient_map[key] = {
                            'name': ing.ingredient.name.capitalize(),
                            'unit': ing.unit,
                            'quantity_per_person': 0,
                            'total_quantity': 0,
                        }

                    ingredient_map[key]['quantity_per_person'] += float(ing.quantity_per_person)

                    if registered_count:
                        ingredient_map[key]['total_quantity'] += (
                            float(ing.quantity_per_person) * registered_count
                        )

        purchase.ingredients_preview = list(ingredient_map.values())

    rejected_dishes = DishRejectLog.objects.select_related(
        'rejected_by'
    ).order_by('-rejected_at')[:20]

    rejected_menus = MenuRejectLog.objects.select_related(
        'rejected_by'
    ).order_by('-rejected_at')[:20]

    rejected_purchases = PurchaseRejectLog.objects.select_related(
        'rejected_by'
    ).order_by('-rejected_at')[:20]

    return render(request, 'meals/approval_dashboard.html', {
        'pending_dishes': pending_dishes,
        'pending_menus': pending_menus,
        'pending_purchases': pending_purchases,
        'rejected_dishes': rejected_dishes,
        'rejected_menus': rejected_menus,
        'rejected_purchases': rejected_purchases,
    })


@login_required
@user_passes_test(can_manage_approval)
def reject_menu(request, pk):
    menu = get_object_or_404(DailyMenu, pk=pk, status=DailyMenu.STATUS_PENDING)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    reject_reason = request.POST.get('reject_reason', '').strip()

    if not reject_reason:
        messages.error(request, 'Bạn phải nhập lý do từ chối.')
        return redirect('approval_dashboard')

    menu_items = list(menu.items.select_related('dish').all())
    menu_snapshot = ', '.join([item.dish.name for item in menu_items])

    created_by_username = ''
    created_by_full_name = ''

    if menu.created_by:
        created_by_username = menu.created_by.username
        profile = getattr(menu.created_by, 'profile', None)
        created_by_full_name = profile.full_name if profile else ''

    MenuRejectLog.objects.create(
        menu=menu,
        date=menu.date,
        reject_reason=reject_reason,
        rejected_by=request.user,
        menu_snapshot=menu_snapshot,
        created_by_username=created_by_username,
        created_by_full_name=created_by_full_name,
    )

    menu.status = DailyMenu.STATUS_REJECTED
    menu.reject_reason = reject_reason
    menu.rejected_by = request.user
    menu.rejected_at = timezone.localtime()
    menu.save()

    messages.success(request, f'Đã từ chối thực đơn ngày {menu.date.strftime("%d/%m/%Y")}.')
    return redirect('approval_dashboard')


@login_required
@user_passes_test(can_manage_approval)
def reject_purchase(request, pk):
    purchase = get_object_or_404(
        DailyPurchase,
        pk=pk,
        status=DailyPurchase.STATUS_PENDING
    )

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    reject_reason = request.POST.get('reject_reason', '').strip()

    if not reject_reason:
        messages.error(request, 'Bạn phải nhập lý do từ chối.')
        return redirect('approval_dashboard')

    created_by_username = ''
    created_by_full_name = ''

    if purchase.created_by:
        created_by_username = purchase.created_by.username
        profile = getattr(purchase.created_by, 'profile', None)
        created_by_full_name = profile.full_name if profile else ''

    PurchaseRejectLog.objects.create(
        purchase=purchase,
        date=purchase.date,
        actual_cost=purchase.actual_cost,
        reject_reason=reject_reason,
        rejected_by=request.user,
        created_by_username=created_by_username,
        created_by_full_name=created_by_full_name,
        note_snapshot=purchase.note,
        bill_image_snapshot=purchase.bill_image,
    )

    purchase.status = DailyPurchase.STATUS_REJECTED
    purchase.reject_reason = reject_reason
    purchase.rejected_by = request.user
    purchase.rejected_at = timezone.localtime()
    purchase.save()

    messages.success(
        request,
        f'Đã từ chối chi phí ngày {purchase.date.strftime("%d/%m/%Y")}.'
    )
    return redirect('approval_dashboard')


@login_required
@user_passes_test(can_manage_approval)
def approve_menu(request, pk):
    menu = get_object_or_404(DailyMenu, pk=pk, status=DailyMenu.STATUS_PENDING)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    menu.status = DailyMenu.STATUS_APPROVED
    menu.save()

    messages.success(request, f'Đã phê duyệt thực đơn ngày {menu.date.strftime("%d/%m/%Y")}.')
    return redirect('approval_dashboard')


@login_required
@user_passes_test(can_manage_approval)
def approve_purchase(request, pk):
    purchase = get_object_or_404(DailyPurchase, pk=pk, status=DailyPurchase.STATUS_PENDING)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    purchase.status = DailyPurchase.STATUS_APPROVED
    purchase.approved_by = request.user
    purchase.approved_at = timezone.localtime()
    purchase.save()

    messages.success(request, f'Đã phê duyệt chi phí ngày {purchase.date.strftime("%d/%m/%Y")}.')
    return redirect('approval_dashboard')
@login_required
@user_passes_test(can_manage_approval)
def approve_dish(request, pk):
    dish = get_object_or_404(Dish, pk=pk, status=Dish.STATUS_PENDING)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    dish.status = Dish.STATUS_APPROVED
    dish.approved_by = request.user
    dish.approved_at = timezone.localtime()
    dish.save()

    messages.success(request, f'Đã phê duyệt món "{dish.name}".')
    return redirect('approval_dashboard')


@login_required
@user_passes_test(can_manage_approval)
def reject_dish(request, pk):
    dish = get_object_or_404(Dish, pk=pk, status=Dish.STATUS_PENDING)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('approval_dashboard')

    reject_reason = request.POST.get('reject_reason', '').strip()

    if not reject_reason:
        messages.error(request, 'Bạn phải nhập lý do từ chối.')
        return redirect('approval_dashboard')

    DishRejectLog.objects.create(
        dish=dish,
        dish_name=dish.name,
        dish_type=dish.dish_type,
        reject_reason=reject_reason,
        rejected_by=request.user,
    )

    dish.status = Dish.STATUS_REJECTED
    dish.reject_reason = reject_reason
    dish.rejected_by = request.user
    dish.rejected_at = timezone.localtime()
    dish.save()

    messages.success(request, f'Đã từ chối món "{dish.name}".')
    return redirect('approval_dashboard')
