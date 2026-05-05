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
            password = form.cleaned_data['password'] or employee_code

            user = User.objects.create_user(
                username=employee_code,
                password=password,
                first_name=full_name,
                email=email,
                is_staff=(role in [UserProfile.ROLE_ADMIN, UserProfile.ROLE_KITCHEN]),
                is_superuser=False,
            )

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
@login_required
def user_profile(request):
    profile = request.user.profile
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'change_avatar':
            avatar = request.FILES.get('avatar')
            if avatar:
                profile.avatar = avatar
                profile.save()
                messages.success(request, 'Đã cập nhật ảnh đại diện.')
            return redirect('user_profile')

        if action == 'change_password':
            password_form = PasswordChangeForm(request.user, request.POST)

            if password_form.is_valid():
                new_password = password_form.cleaned_data.get('new_password1')
                old_password = password_form.cleaned_data.get('old_password')

                # 🔥 check trùng mật khẩu cũ
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

    return render(request, 'accounts/user_profile.html', {
        'profile': profile,
        'password_form': password_form,
    })


@login_required
@user_passes_test(can_manage_user)
def reset_user_password(request, pk):
    user = get_object_or_404(User.objects.select_related('profile'), pk=pk)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('user_list')

    employee_code = user.profile.employee_code or user.username
    user.set_password(employee_code)
    user.save()

    messages.success(request, f'Đã reset mật khẩu của {user.username} về mã nhân viên.')
    return redirect('user_list')
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