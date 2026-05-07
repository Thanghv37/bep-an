from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import render, redirect
from django.db.models import Sum
from accounts.models import UserProfile
from accounts.permissions import can_manage_menu
from .forms import MealRegistrationForm
from .import_utils import import_registrations_from_excel
from .models import MealRegistration
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from core.models import AttendanceLog
from django.utils.timezone import now
def is_admin(user):
    return user.is_staff  # hoặc is_superuser
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

    status_choices = MealRegistration.objects.exclude(status='').values_list(
        'status', flat=True
    ).distinct().order_by('status')

    meal_choices = MealRegistration.objects.exclude(meal_name='').values_list(
        'meal_name', flat=True
    ).distinct().order_by('meal_name')

    kitchen_choices = MealRegistration.objects.exclude(kitchen_name='').values_list(
        'kitchen_name', flat=True
    ).distinct().order_by('kitchen_name')

    return render(request, 'registrations/registration_list.html', {
        'rows': rows,
        'selected_date': selected_date,
        'keyword': keyword,
        'status_filter': status_filter,
        'meal_filter': meal_filter,
        'kitchen_filter': kitchen_filter,
        'status_choices': status_choices,
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

    return redirect('registration_list')


@login_required
@user_passes_test(can_manage_menu)
def registration_create(request):
    if request.method == 'POST':
        form = MealRegistrationForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.source = 'manual'
            obj.save()

            messages.success(request, 'Đã thêm đăng kí suất ăn.')
            return redirect('registration_list')
    else:
        form = MealRegistrationForm(initial={
            'date': date.today(),
            'quantity': 1,
        })

    return render(request, 'registrations/registration_form.html', {
        'form': form,
        'page_title': 'Thêm người đăng kí',
        'submit_label': 'Lưu đăng kí',
    })
@login_required
@user_passes_test(is_admin)
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

    if not request.user.is_superuser:
        return HttpResponseForbidden("Bạn không có quyền xóa dữ liệu.")

    if request.method == 'POST':
        deleted_count, _ = MealRegistration.objects.all().delete()

        messages.success(
            request,
            f'Đã xóa toàn bộ {deleted_count} đăng ký.'
        )

    return redirect('registration_list')
@login_required
@user_passes_test(is_admin)
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

    # Lọc theo tên/mã nhân viên và trạng thái
    q_name = request.GET.get('q_name', '').strip()
    q_status = request.GET.get('q_status', '').strip()

    logs = AttendanceLog.objects.filter(scan_time__date=target_date)
    if q_name:
        logs = logs.filter(full_name__icontains=q_name)
    if q_status:
        logs = logs.filter(status=q_status)

    context = {
        'logs': logs.order_by('scan_time'),
        'target_date': target_date,
        'q_name': q_name,
        'q_status': q_status,
    }
    return render(request, 'registrations/registration_participation.html', context)