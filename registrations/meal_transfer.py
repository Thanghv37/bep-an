"""Logic cho module Chuyển suất ăn.

Tách riêng khỏi views.py để dễ test + tái sử dụng (hook sau import Excel,
management command cancel hết hạn, NetChat noti).

Luồng cho 1 yêu cầu chuyển A -> B ngày X:
- Tạo transfer (status=pending) hoặc apply ngay nếu đã có data đăng ký A.
- Apply: với mỗi MealRegistration A ngày X, đổi sang B. Nếu B đã có
  MealRegistration cùng (date, meal_name, kitchen_name) -> cộng quantity vào
  của B, xóa của A để tránh vi phạm unique_together.
- Expiry: pending còn lại sau 11h ngày X -> auto cancel với reason.
"""
from datetime import datetime, time
import logging

from django.db import transaction
from django.utils import timezone

from .models import MealRegistration, MealTransfer


logger = logging.getLogger(__name__)

# Cutoff: trước 11h ngày X (giờ VN) mới được tạo / pending mới apply được.
CUTOFF_HOUR = 11


def cutoff_datetime_for(meal_date):
    """Trả về datetime tz-aware (VN) ứng với 11h ngày meal_date."""
    tz = timezone.get_current_timezone()
    naive = datetime.combine(meal_date, time(CUTOFF_HOUR, 0))
    return timezone.make_aware(naive, tz)


def is_within_cutoff(meal_date, now=None):
    """True nếu vẫn còn được phép chuyển suất cho meal_date."""
    now = now or timezone.now()
    return now < cutoff_datetime_for(meal_date)


def apply_meal_transfer(transfer):
    """Apply 1 transfer: đổi MealRegistration của A sang B.

    Trả về (status, keys):
    - ('applied', [(meal, kitchen), ...]) — đã chuyển, kèm danh sách (bữa, bếp).
    - ('a_not_registered', []) — A chưa có đăng ký ngày này (caller có thể giữ
      pending để chờ data sync, hoặc cancel nếu đã quá hạn).
    - ('b_already_registered', [(meal, kitchen), ...]) — B đã có đăng ký trùng
      ít nhất 1 (bữa, bếp) với A. KHÔNG chuyển gì (all-or-nothing), caller
      cancel transfer + báo cho 2 bên.
    """
    a_regs = list(MealRegistration.objects.filter(
        employee_code=transfer.from_employee_code,
        date=transfer.meal_date,
    ))
    if not a_regs:
        return 'a_not_registered', []

    a_keys = [(r.meal_name, r.kitchen_name) for r in a_regs]
    b_pairs = MealRegistration.objects.filter(
        employee_code=transfer.to_employee_code,
        date=transfer.meal_date,
    ).values_list('meal_name', 'kitchen_name')
    b_keys = {(m, k) for m, k in b_pairs}
    overlap = [k for k in a_keys if k in b_keys]
    if overlap:
        return 'b_already_registered', overlap

    with transaction.atomic():
        for reg in MealRegistration.objects.filter(
                employee_code=transfer.from_employee_code,
                date=transfer.meal_date,
        ).select_for_update():
            reg.employee_code = transfer.to_employee_code
            reg.full_name = transfer.to_full_name or reg.full_name
            reg.source = 'transfer'
            reg.save(update_fields=['employee_code', 'full_name', 'source', 'updated_at'])

        transfer.status = MealTransfer.STATUS_APPLIED
        transfer.applied_at = timezone.now()
        transfer.save(update_fields=['status', 'applied_at'])

    return 'applied', a_keys


def apply_pending_transfers_for_date(target_date):
    """Lặp qua mọi transfer pending ngày target_date, apply nếu có data A."""
    pending = MealTransfer.objects.filter(
        meal_date=target_date,
        status=MealTransfer.STATUS_PENDING,
    )
    return _apply_queryset(pending)


def apply_all_pending_transfers():
    """Apply mọi pending có data A — gọi sau khi import Excel (không biết
    chính xác ngày nào được import, cứ thử hết). Pending không có data A
    vẫn giữ pending, sẽ bị cancel sau 11h ngày X.
    """
    pending = MealTransfer.objects.filter(status=MealTransfer.STATUS_PENDING)
    return _apply_queryset(pending)


def _apply_queryset(qs):
    applied = 0
    failed_b_conflict = 0
    still_pending = 0
    for tr in qs:
        status, keys = apply_meal_transfer(tr)
        if status == 'applied':
            applied += 1
            _safe_send_netchat(tr, 'applied', transferred_keys=keys)
        elif status == 'b_already_registered':
            tr.status = MealTransfer.STATUS_CANCELLED
            tr.cancel_reason = 'Người nhận đã có đăng ký trùng bữa/bếp.'
            tr.save(update_fields=['status', 'cancel_reason'])
            failed_b_conflict += 1
            _safe_send_netchat(tr, 'failed_b_conflict', conflict_keys=keys)
        else:
            # 'a_not_registered' -> giữ pending, sẽ chờ data hoặc bị expire hủy.
            still_pending += 1
    return {'applied': applied, 'failed': failed_b_conflict, 'still_pending': still_pending}


def cancel_expired_transfers(now=None):
    """Cancel pending đã quá 11h ngày X (A chưa đăng ký kịp).

    Áp dụng cho cả:
    - meal_date < today (đã qua mà data A không xuất hiện)
    - meal_date == today AND now >= 11h

    Gửi NetChat cho A + B với lý do "A chưa đăng ký".
    """
    now = now or timezone.now()
    today = timezone.localdate(now)
    cancelled = 0

    pending_today_after_cutoff = MealTransfer.objects.filter(
        meal_date=today,
        status=MealTransfer.STATUS_PENDING,
    )
    for tr in pending_today_after_cutoff:
        if now >= cutoff_datetime_for(tr.meal_date):
            _cancel(tr, 'A chưa đăng ký suất ăn ngày này.', event='failed_a_not_registered')
            cancelled += 1

    pending_past = MealTransfer.objects.filter(
        meal_date__lt=today,
        status=MealTransfer.STATUS_PENDING,
    )
    for tr in pending_past:
        _cancel(tr, 'A chưa đăng ký suất ăn ngày này.', event='failed_a_not_registered')
        cancelled += 1

    return cancelled


def _cancel(transfer, reason, event='cancelled'):
    transfer.status = MealTransfer.STATUS_CANCELLED
    transfer.cancel_reason = reason
    transfer.save(update_fields=['status', 'cancel_reason'])
    _safe_send_netchat(transfer, event)


def _safe_send_netchat(transfer, event, **kwargs):
    """Wrap NetChat send để lỗi mạng không làm fail luồng chính."""
    try:
        from .meal_transfer_notify import send_transfer_netchat
        send_transfer_netchat(transfer, event, **kwargs)
    except Exception as e:
        logger.warning('NetChat noti transfer %s event=%s lỗi: %s',
                       transfer.pk, event, e)
