from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from accounts.permissions import can_manage_user
from .forms import UserCreateForm, UserUpdateForm
from .models import UserProfile
from .forms import ImportUserForm
from .import_utils import import_users_from_excel
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from core.models import SystemConfig
import requests
from django.http import JsonResponse
import json
import secrets
from django.utils import timezone
from django.contrib.auth import login as auth_login
from .models import OTPToken, UserProfile
from core.models import SystemConfig # Để lấy cấu hình Bot

# --- HÀM 1: GỬI MÃ OTP QUA NETCHAT ---
def request_otp(request):
    if request.method == 'POST':
        employee_code = request.POST.get('employee_code', '').strip()
        
        try:
            # 1. Kiểm tra nhân viên có tồn tại không
            user_profile = UserProfile.objects.get(employee_code=employee_code)
            email = user_profile.email
            if not email:
                messages.error(request, "Tài khoản chưa cập nhật Email, không thể gửi OTP.")
                return redirect('login')
            
            # 2. Tạo mã OTP 6 số (Dùng secrets cho bảo mật giống Net2ID)
            otp_code = str(secrets.randbelow(900000) + 100000)
            
            # 3. Lưu OTP vào Database
            OTPToken.objects.create(employee_code=employee_code, otp_code=otp_code)
            
            # 4. Lấy cấu hình Bot để gửi tin
            config_url = SystemConfig.objects.filter(key='netchat_url').first()
            config_token = SystemConfig.objects.filter(key='netchat_token').first()
            
            if not config_url or not config_token:
                messages.error(request, "Hệ thống chưa cấu hình BOT. Vui lòng liên hệ Admin.")
                return redirect('login')

            # 5. Tiến hành gửi qua NetChat
            url = config_url.value.strip().rstrip('/')
            token = config_token.value.strip()
            username = email.split('@')[0].strip().lower()
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "curl/8.7.1" # Vượt tường lửa
            }

            # A. Lấy ID của Bot và User
            r_me = requests.get(f"{url}/api/v4/users/me", headers=headers, timeout=5)
            r_user = requests.get(f"{url}/api/v4/users/username/{username}", headers=headers, timeout=5)
            
            if r_me.status_code == 200 and r_user.status_code == 200:
                bot_id = r_me.json().get('id')
                user_mm_id = r_user.json().get('id')
                
                # B. Mở kênh DM và gửi tin
                r_chan = requests.post(f"{url}/api/v4/channels/direct", headers=headers, json=[bot_id, user_mm_id])
                channel_id = r_chan.json().get('id')
                
                from core.message_templates import get_otp_template, render_template
                msg = render_template(
                    get_otp_template(),
                    otp_code=otp_code,
                    employee_code=employee_code,
                    full_name=user_profile.full_name or '',
                )
                requests.post(f"{url}/api/v4/posts", headers=headers, json={"channel_id": channel_id, "message": msg})
                
                # 6. Thành công: Lưu employee_code vào session và chuyển sang trang nhập mã
                request.session['pending_employee_code'] = employee_code
                return redirect('verify_otp')
            else:
                messages.error(request, "Không thể gửi tin nhắn qua NetChat. Hãy chắc chắn bạn đã đăng nhập NetChat.")
                
        except UserProfile.DoesNotExist:
            messages.error(request, "Mã nhân viên không tồn tại trong hệ thống.")
            
    return redirect('login')

# --- HÀM 2: XÁC THỰC OTP VÀ ĐĂNG NHẬP ---
def verify_otp(request):
    employee_code = request.session.get('pending_employee_code')
    if not employee_code:
        return redirect('login')

    if request.method == 'POST':
        otp_input = request.POST.get('otp_code', '').strip()
        
        # Lấy mã OTP mới nhất
        otp_record = OTPToken.objects.filter(
            employee_code=employee_code, 
            otp_code=otp_input,
            is_used=False
        ).order_by('-created_at').first()

        if otp_record and otp_record.is_valid():
            otp_record.is_used = True
            otp_record.save()
            
            try:
                user = User.objects.get(username=employee_code)
                
                # BẮT BUỘC: Gán backend xác thực để Django duy trì phiên đăng nhập
                if not hasattr(user, 'backend'):
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                
                # Đăng nhập vào hệ thống
                auth_login(request, user)
                
                # Tối ưu: Lưu session ngay lập tức để tránh lỗi race condition
                request.session.modified = True 
                
                # Xóa mã tạm trong session
                if 'pending_employee_code' in request.session:
                    del request.session['pending_employee_code']
                
                messages.success(request, f"Đăng nhập thành công! Chào {user.first_name or user.username}.")
                
                # YÊU CẦU: 100% chuyển hướng về Dashboard chính
                return redirect('/') 
                
            except User.DoesNotExist:
                messages.error(request, "Lỗi: Tài khoản không tồn tại.")
        else:
            messages.error(request, "Mã OTP không chính xác hoặc đã hết hạn.")

    return render(request, 'registration/otp_verify.html', {'employee_code': employee_code})

@login_required
@user_passes_test(can_manage_user)
def user_list(request):
    keyword = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', 'all').strip()
    unit_filter = request.GET.get('unit', '').strip()
    department_filter = request.GET.get('department', '').strip()

    users = User.objects.select_related('profile').order_by(
        'profile__employee_code',
        'username'
    )

    if keyword:
        users = users.filter(
            Q(username__icontains=keyword) |
            Q(profile__employee_code__icontains=keyword) |
            Q(profile__full_name__icontains=keyword)
        )

    if role_filter in ['admin', 'kitchen', 'diner']:
        users = users.filter(profile__role=role_filter)

    if unit_filter:
        users = users.filter(profile__unit=unit_filter)

    if department_filter:
        users = users.filter(profile__department=department_filter)

    unit_choices = UserProfile.objects.exclude(
        unit=''
    ).values_list('unit', flat=True).distinct().order_by('unit')

    department_choices = UserProfile.objects.exclude(
        department=''
    ).values_list('department', flat=True).distinct().order_by('department')

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'keyword': keyword,
        'active_role': role_filter,
        'unit_filter': unit_filter,
        'department_filter': department_filter,
        'unit_choices': unit_choices,
        'department_choices': department_choices,
    })


def _get_profile_choices():
    return {
        'unit_choices': list(UserProfile.objects.exclude(unit='').exclude(unit__iexact='none').values_list('unit', flat=True).distinct().order_by('unit')),
        'department_choices': list(UserProfile.objects.exclude(department='').exclude(department__iexact='none').values_list('department', flat=True).distinct().order_by('department')),
        'position_choices': list(UserProfile.objects.exclude(position='').exclude(position__iexact='none').values_list('position', flat=True).distinct().order_by('position')),
    }


@login_required
@user_passes_test(can_manage_user)
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)

        if form.is_valid():
            employee_code = form.cleaned_data['employee_code']
            full_name = form.cleaned_data['full_name']
            email = form.cleaned_data.get('email', '')
            gender = form.cleaned_data.get('gender', '')
            unit = form.cleaned_data.get('unit', '')
            phone = form.cleaned_data.get('phone', '')
            position = form.cleaned_data['position']
            department = form.cleaned_data['department']
            role = form.cleaned_data['role']

            user = User.objects.create_user(
                username=employee_code,
                first_name=full_name,
                email=email,
                is_staff=(role in [UserProfile.ROLE_ADMIN, UserProfile.ROLE_KITCHEN]),
                is_superuser=False,
            )
            user.set_unusable_password()
            user.save()

            profile = user.profile
            profile.employee_code = employee_code
            profile.full_name = full_name
            profile.email = email
            profile.gender = gender
            profile.unit = unit
            profile.department = department
            profile.position = position
            profile.phone = phone
            profile.role = role
            profile.save()

            messages.success(request, f'Đã tạo người dùng {full_name}.')
            return redirect('user_list')
    else:
        form = UserCreateForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'page_title': 'Thêm người dùng',
        'submit_label': 'Tạo người dùng',
        **_get_profile_choices(),
    })


@login_required
@user_passes_test(can_manage_user)
def user_update(request, pk):
    user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    profile = user.profile

    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=profile)

        if form.is_valid():
            profile = form.save()

            user.username = profile.employee_code or user.username
            user.first_name = profile.full_name
            user.email = profile.email
            user.is_staff = profile.role in [
                UserProfile.ROLE_ADMIN,
                UserProfile.ROLE_KITCHEN
            ]
            user.save()

            messages.success(request, 'Đã cập nhật người dùng.')
            return redirect('user_list')
    else:
        form = UserUpdateForm(instance=profile)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'page_title': 'Cập nhật người dùng',
        'submit_label': 'Cập nhật',
        **_get_profile_choices(),
    })


@login_required
@user_passes_test(can_manage_user)
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('user_list')

    if user == request.user:
        messages.error(request, 'Bạn không thể xóa chính tài khoản đang đăng nhập.')
        return redirect('user_list')

    if user.is_superuser:
        messages.error(request, 'Không thể xóa tài khoản superuser.')
        return redirect('user_list')

    username = user.username
    user.delete()

    messages.success(request, f'Đã xóa người dùng {username}.')
    return redirect('user_list')


@login_required
@user_passes_test(can_manage_user)
def import_users(request):
    if request.method == 'POST':
        form = ImportUserForm(request.POST, request.FILES)

        if form.is_valid():
            file = form.cleaned_data['file']

            created, updated, errors = import_users_from_excel(file)

            messages.success(
                request,
                f'Import thành công: {created} tạo mới, {updated} cập nhật.'
            )

            if errors:
                messages.warning(request, 'Có lỗi xảy ra:')
                for err in errors[:10]:
                    messages.warning(request, err)

            return redirect('user_list')
    else:
        form = ImportUserForm()

    return render(request, 'accounts/import_users.html', {
        'form': form,
    })
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect
from django.contrib import messages
# TODO: Đảm bảo bạn đã import PasswordChangeForm ở đầu file
# from django.contrib.auth.forms import PasswordChangeForm

# TODO: Import model lưu cấu hình của bạn, ví dụ (nếu bạn tạo model SystemConfig):
# from core.models import SystemConfig 

@login_required
def user_profile(request):
    profile = request.user.profile
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. XỬ LÝ ĐỔI ẢNH ĐẠI DIỆN
        if action == 'change_avatar':
            avatar = request.FILES.get('avatar')
            if avatar:
                profile.avatar = avatar
                profile.save()
                messages.success(request, 'Đã cập nhật ảnh đại diện.')
            return redirect('user_profile')

        # 2. XỬ LÝ ĐỔI MẬT KHẨU
        if action == 'change_password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                new_password = password_form.cleaned_data.get('new_password1')
                if request.user.check_password(new_password):
                    password_form.add_error('new_password1', 'Mật khẩu mới không được trùng mật khẩu cũ.')
                    messages.error(request, 'Mật khẩu mới không được trùng mật khẩu cũ.')
                else:
                    user = password_form.save()
                    update_session_auth_hash(request, user)
                    messages.success(request, 'Đã đổi mật khẩu thành công.')
                    return redirect('user_profile')
            else:
                messages.error(request, 'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại thông tin.')

        # 3. XỬ LÝ LƯU CẤU HÌNH BOT NETCHAT
        # Kiểm tra quyền ADMIN hoặc Superuser
        is_admin = request.user.is_superuser or getattr(profile, 'role', '').lower() == 'admin'

        if action == 'save_bot_config' and is_admin:
            url = request.POST.get('netchat_url', '').strip()
            token = request.POST.get('netchat_token', '').strip()

            # Lưu vào Database
            SystemConfig.objects.update_or_create(key='netchat_url', defaults={'value': url})
            SystemConfig.objects.update_or_create(key='netchat_token', defaults={'value': token})

            messages.success(request, 'Đã lưu cấu hình BOT NetChat thành công.')
            return redirect('user_profile')

        # 4. XỬ LÝ LƯU TEMPLATE TIN NHẮN OTP / ĐẶT CƠM
        if action in ('save_msg_otp', 'save_msg_meal') and is_admin:
            from core.message_templates import KEY_OTP, KEY_MEAL

            template_value = request.POST.get('template_value', '').strip()
            cfg_key = KEY_OTP if action == 'save_msg_otp' else KEY_MEAL
            label = 'OTP' if action == 'save_msg_otp' else 'đặt cơm'

            SystemConfig.objects.update_or_create(key=cfg_key, defaults={'value': template_value})
            messages.success(request, f'Đã lưu mẫu tin nhắn {label}.')
            return redirect('user_profile')

    # 5. TRUY VẤN DỮ LIỆU ĐỂ HIỂN THỊ
    config_url = SystemConfig.objects.filter(key='netchat_url').first()
    config_token = SystemConfig.objects.filter(key='netchat_token').first()

    bot_config = {
        'netchat_url': config_url.value if config_url else '',
        'netchat_token': config_token.value if config_token else '',
    }

    from core.message_templates import (
        get_otp_template, get_meal_template,
        VARS_OTP, VARS_MEAL,
    )
    msg_templates = {
        'otp': get_otp_template(),
        'meal': get_meal_template(),
        'otp_vars': VARS_OTP,
        'meal_vars': VARS_MEAL,
    }

    return render(request, 'accounts/user_profile.html', {
        'profile': profile,
        'password_form': password_form,
        'bot_config': bot_config,
        'msg_templates': msg_templates,
    })


@require_GET
def users_api(request):
    profiles = UserProfile.objects.exclude(
        employee_code__isnull=True
    ).exclude(
        employee_code=''
    ).order_by('employee_code')

    dict_users = {}

    for profile in profiles:
        employee_code = str(profile.employee_code).strip()
        full_name = profile.full_name or profile.user.get_full_name() or profile.user.username

        dict_users[employee_code] = full_name

    return JsonResponse({
        'total_users': len(dict_users),
        'dict_users': dict_users,
    }, json_dumps_params={
        'ensure_ascii': False
    })
@login_required
def verify_bot_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url', '').strip().rstrip('/')
            token = data.get('token', '').strip()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "curl/8.7.1"
            }
            
            # Gọi thử đến Mattermost để check token
            response = requests.get(f"{url}/api/v4/users/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                bot_data = response.json()
                return JsonResponse({
                    'success': True, 
                    'bot_name': bot_data.get('full_name') or bot_data.get('username')
                })
            else:
                return JsonResponse({'success': False, 'message': 'Token không hợp lệ hoặc sai URL.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)