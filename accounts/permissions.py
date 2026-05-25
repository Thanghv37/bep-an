from .models import UserProfile


def get_user_role(user):
    if not user.is_authenticated:
        return None

    if user.is_superuser:
        return UserProfile.ROLE_ADMIN

    profile = getattr(user, 'profile', None)
    if profile:
        return profile.role

    return None


def is_admin(user):
    return user.is_authenticated and get_user_role(user) == UserProfile.ROLE_ADMIN


def is_kitchen(user):
    return user.is_authenticated and get_user_role(user) == UserProfile.ROLE_KITCHEN


def is_diner(user):
    return user.is_authenticated and get_user_role(user) == UserProfile.ROLE_DINER


def can_view_dashboard(user):
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
        UserProfile.ROLE_DINER,
    ]


def can_view_report(user):
    return can_view_dashboard(user)


def can_export_report(user):
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
    ]


def can_manage_dish(user):
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
    ]


def can_manage_menu(user):
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
    ]


def can_manage_purchase(user):
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
    ]


def can_manage_meal_price(user):
    return is_admin(user)


def can_manage_user(user):
    return is_admin(user)


def can_view_user_list(user):
    """Xem danh sách người dùng — admin (đầy đủ quyền) + kitchen (chỉ xem,
    để đối chiếu mã NV / tên)."""
    return user.is_authenticated and get_user_role(user) in [
        UserProfile.ROLE_ADMIN,
        UserProfile.ROLE_KITCHEN,
    ]


def can_manage_approval(user):
    return is_admin(user)