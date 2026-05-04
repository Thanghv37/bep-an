from meals.models import DailyMenu
from finance.models import DailyPurchase


def approval_counts(request):
    if not request.user.is_authenticated:
        return {
            'pending_approval_count': 0,
        }

    if not (request.user.is_superuser or getattr(request.user.profile, 'role', None) == 'admin'):
        return {
            'pending_approval_count': 0,
        }

    pending_menu_count = DailyMenu.objects.filter(
        status=DailyMenu.STATUS_PENDING
    ).count()

    pending_purchase_count = DailyPurchase.objects.filter(
        status=DailyPurchase.STATUS_PENDING
    ).count()

    return {
        'pending_approval_count': pending_menu_count + pending_purchase_count,
    }