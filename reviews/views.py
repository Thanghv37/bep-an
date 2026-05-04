from calendar import monthrange
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import render, redirect, get_object_or_404

from meals.models import DailyMenu
from .forms import MealReviewForm
from .models import MealReview


def can_review_date(target_date):
    today = date.today()
    allowed_start = today - timedelta(days=1)
    return allowed_start <= target_date <= today


def get_stats_range(selected_date, stats_mode):
    if stats_mode == 'week':
        start_date = selected_date - timedelta(days=selected_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif stats_mode == 'month':
        start_date = date(selected_date.year, selected_date.month, 1)
        end_date = date(
            selected_date.year,
            selected_date.month,
            monthrange(selected_date.year, selected_date.month)[1]
        )
    else:
        start_date = selected_date
        end_date = selected_date

    return start_date, end_date


@login_required
def review_dashboard(request):
    selected_date_str = request.GET.get('date')

    if selected_date_str:
        try:
            selected_date = date.fromisoformat(selected_date_str)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    stats_mode = request.GET.get('stats_mode', 'day')

    try:
        stats_date = date.fromisoformat(request.GET.get('stats_date')) if request.GET.get('stats_date') else selected_date
    except ValueError:
        stats_date = selected_date

    try:
        stats_month = int(request.GET.get('stats_month', stats_date.month))
    except (ValueError, TypeError):
        stats_month = stats_date.month

    try:
        stats_year = int(request.GET.get('stats_year', stats_date.year))
    except (ValueError, TypeError):
        stats_year = stats_date.year

    if stats_month < 1 or stats_month > 12:
        stats_month = stats_date.month

    can_review = can_review_date(selected_date)

    menu = DailyMenu.objects.filter(
        date=selected_date,
        status=DailyMenu.STATUS_APPROVED
    ).prefetch_related('items__dish').first()

    existing_review = MealReview.objects.filter(
        date=selected_date,
        user=request.user
    ).first()

    if request.method == 'POST':
        if not can_review:
            messages.error(request, 'Đã hết thời gian đánh giá cho ngày này.')
            return redirect(f'/reviews/?date={selected_date.isoformat()}&stats_mode={stats_mode}')

        form = MealReviewForm(request.POST, instance=existing_review)

        if form.is_valid():
            review = form.save(commit=False)
            review.date = selected_date
            review.user = request.user
            review.save()

            messages.success(request, 'Đã lưu đánh giá của bạn.')
            return redirect(f'/reviews/?date={selected_date.isoformat()}&stats_mode={stats_mode}')
    else:
        form = MealReviewForm(instance=existing_review)

    # Tổng hợp theo ngày / tuần / tháng
    if stats_mode == 'month':
        stats_base_date = date(stats_year, stats_month, 1)
    else:
        stats_base_date = stats_date

    stats_start_date, stats_end_date = get_stats_range(stats_base_date, stats_mode)

    stat_reviews = MealReview.objects.filter(
        date__range=(stats_start_date, stats_end_date)
    ).select_related('user', 'user__profile')

    stats = stat_reviews.aggregate(
        review_count=Count('id'),
        avg_food_quality=Avg('food_quality_score'),
        avg_taste=Avg('taste_score'),
        avg_freshness=Avg('freshness_score'),
        avg_portion=Avg('portion_score'),
        avg_hygiene=Avg('hygiene_score'),
        avg_overall=Avg('overall_score'),
    )

    comment_reviews = stat_reviews.order_by('-updated_at')[:20]

    # Lịch mini trong tháng
    try:
        selected_month = int(request.GET.get('month', selected_date.month))
    except (ValueError, TypeError):
        selected_month = selected_date.month

    try:
        selected_year = int(request.GET.get('year', selected_date.year))
    except (ValueError, TypeError):
        selected_year = selected_date.year

    if selected_month < 1 or selected_month > 12:
        selected_month = selected_date.month

    month_start = date(selected_year, selected_month, 1)
    month_end = date(
        selected_year,
        selected_month,
        monthrange(selected_year, selected_month)[1]
    )

    month_stats = MealReview.objects.filter(
        date__range=(month_start, month_end)
    ).values('date').annotate(
        review_count=Count('id'),
        avg_overall=Avg('overall_score')
    )

    month_stats_map = {
        item['date']: item
        for item in month_stats
    }

    day_cards = []
    current_date = month_start

    while current_date <= month_end:
        item = month_stats_map.get(current_date)

        day_cards.append({
            'date': current_date,
            'date_str': current_date.isoformat(),
            'date_label': current_date.strftime('%d/%m'),
            'day': current_date.day,
            'is_selected': current_date == selected_date,
            'can_review': can_review_date(current_date),
            'review_count': item['review_count'] if item else 0,
            'avg_overall': round(item['avg_overall'], 1) if item and item['avg_overall'] is not None else None,
        })

        current_date += timedelta(days=1)

    context = {
        'selected_date': selected_date,
        'selected_date_str': selected_date.isoformat(),
        'can_review': can_review,
        'menu': menu,
        'form': form,
        'existing_review': existing_review,
        'stats': stats,
        'comment_reviews': comment_reviews,
        'day_cards': day_cards,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'month_choices': list(range(1, 13)),
        'year_choices': list(range(date.today().year - 2, date.today().year + 3)),
        'stats_mode': stats_mode,
        'stats_start_date': stats_start_date,
        'stats_end_date': stats_end_date,
        'stats_date': stats_date,
        'stats_date_str': stats_date.isoformat(),
        'stats_month': stats_month,
        'stats_year': stats_year,
    }

    return render(request, 'reviews/review_dashboard.html', context)


@login_required
def review_delete(request, pk):
    review = get_object_or_404(MealReview, pk=pk, user=request.user)

    if request.method != 'POST':
        messages.error(request, 'Yêu cầu không hợp lệ.')
        return redirect('review_dashboard')

    if not can_review_date(review.date):
        messages.error(request, 'Đã hết thời gian xóa đánh giá cho ngày này.')
        return redirect(f'/reviews/?date={review.date.isoformat()}')

    review_date = review.date
    review.delete()

    messages.success(request, 'Đã xóa đánh giá của bạn.')
    return redirect(f'/reviews/?date={review_date.isoformat()}')