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
import threading
import time
import requests
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from accounts.models import UserProfile
from .models import MealRegistration, NotificationLog
from core.models import SystemConfig  # Import bảng cấu hình Bot của bạn nếu có


def is_admin(user):
    return user.is_staff  # hoặc is_superuser
@login_required
#@user_passes_test(can_manage_menu)
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
# --- HÀM CHẠY NGẦM GỬI TIN NHẮN (BACKGROUND THREAD) ---
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

    success_count = 0
    
    # 2. Vòng lặp gửi tin nhắn
    for i, emp_code in enumerate(employee_codes):
        # Logic chống Spam: Đủ 15 người thì ngủ 60s
        if i > 0 and i % 15 == 0:
            print(f"[NetChat] Đã gửi {i} tin. Tạm nghỉ 60s để tránh spam...")
            time.sleep(60)

        profile = profile_dict.get(emp_code)
        reg = reg_dict.get(emp_code)
        
        if not profile or not profile.email or not reg:
            print(f"[NetChat] Bỏ qua {emp_code}: Thiếu profile, email hoặc chưa đăng ký bữa ăn.")
            continue

        # Trích xuất username từ email (Bỏ đuôi @viettel.com.vn)
        username = profile.email.split('@')[0].strip().lower()
        full_name = profile.full_name or reg.full_name

        try:
            # Bước A: Tìm Mattermost ID theo Username
            r_user = requests.get(f"{netchat_url}/api/v4/users/username/{username}", headers=headers, timeout=10)
            if r_user.status_code != 200:
                print(f"[NetChat] Bỏ qua {username}: Không tìm thấy tài khoản trên NetChat Viettel.")
                NotificationLog.objects.create(
                    target_date=target_date,
                    employee_code=emp_code,
                    full_name=full_name,
                    status='failed',
                    error_message='Không tìm thấy tài khoản trên NetChat'
                )
                continue # Bỏ qua nếu user chưa có trên NetChat
            mm_user_id = r_user.json().get('id')

            # Bước B: Mở Direct Message (DM)
            r_channel = requests.post(
                f"{netchat_url}/api/v4/channels/direct", 
                headers=headers, json=[bot_id, mm_user_id], timeout=10
            )
            if r_channel.status_code not in (200, 201):
                NotificationLog.objects.create(
                    target_date=target_date,
                    employee_code=emp_code,
                    full_name=full_name,
                    status='failed',
                    error_message=f'Lỗi mở kênh chat: {r_channel.text}'
                )
                continue
            channel_id = r_channel.json().get('id')

            # Bước C: Gửi tin nhắn (template lấy từ SystemConfig)
            from core.message_templates import get_meal_template, render_template
            message = render_template(
                get_meal_template(),
                full_name=full_name,
                employee_code=emp_code,
                meal_name=reg.meal_name,
                target_date=target_date,
                kitchen_name=reg.kitchen_name,
            )
            
            r_post = requests.post(
                f"{netchat_url}/api/v4/posts", 
                headers=headers, json={"channel_id": channel_id, "message": message}, timeout=10
            )
            
            if r_post.status_code in (200, 201):
                success_count += 1
                NotificationLog.objects.create(
                    target_date=target_date,
                    employee_code=emp_code,
                    full_name=full_name,
                    status='success'
                )
            else:
                NotificationLog.objects.create(
                    target_date=target_date,
                    employee_code=emp_code,
                    full_name=full_name,
                    status='failed',
                    error_message=f'Lỗi gửi tin: {r_post.text}'
                )

        except Exception as e:
            print(f"[NetChat] Lỗi gửi cho {username}: {str(e)}")
            NotificationLog.objects.create(
                target_date=target_date,
                employee_code=emp_code,
                full_name=full_name,
                status='failed',
                error_message=str(e)[:500]
            )
            continue

    print(f"[NetChat] Hoàn tất tiến trình. Thành công: {success_count}/{len(employee_codes)}")


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
        
    return JsonResponse({
        'success': True,
        'success_count': success_count,
        'failed_count': failed_count,
        'logs': log_data
    })