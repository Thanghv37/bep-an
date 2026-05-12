from calendar import monthrange
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from meals.models import DailyMenu
from django.core.paginator import Paginator

from .forms import MealReviewForm
from .models import MealReview, DishReview


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

            # Đánh giá món ăn giờ lưu qua API ajax_review_dish


            messages.success(request, 'Đã lưu đánh giá của bạn.')
            return redirect(f'/reviews/?date={selected_date.isoformat()}&stats_mode={stats_mode}')
    else:
        form = MealReviewForm(instance=existing_review)

    existing_dish_reviews = {}
    if existing_review:
        user_dish_reviews = DishReview.objects.filter(meal_review=existing_review)
        for dr in user_dish_reviews:
            existing_dish_reviews[dr.dish_id] = dr.evaluation
            
    # Tính tổng số Like/Dislike của ngày đó cho mỗi món
    dish_stats_for_day = DishReview.objects.filter(
        meal_review__date=selected_date
    ).values('dish_id', 'evaluation').annotate(count=Count('id'))

    dish_counts = {}
    for stat in dish_stats_for_day:
        d_id = stat['dish_id']
        if d_id not in dish_counts:
            dish_counts[d_id] = {'likes': 0, 'dislikes': 0}
        
        if stat['evaluation'] == DishReview.LIKE:
            dish_counts[d_id]['likes'] = stat['count']
        elif stat['evaluation'] == DishReview.DISLIKE:
            dish_counts[d_id]['dislikes'] = stat['count']
            
    if menu:
        for item in menu.items.all():
            item.user_evaluation = existing_dish_reviews.get(item.dish.id)
            item.likes_count = dish_counts.get(item.dish.id, {}).get('likes', 0)
            item.dislikes_count = dish_counts.get(item.dish.id, {}).get('dislikes', 0)

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
        review_count=Count('id')
    )
    
    dish_stats = DishReview.objects.filter(
        meal_review__date__range=(stats_start_date, stats_end_date)
    ).aggregate(
        total_likes=Count('id', filter=Q(evaluation=DishReview.LIKE)),
        total_dislikes=Count('id', filter=Q(evaluation=DishReview.DISLIKE)),
    )
    
    stats['total_likes'] = dish_stats['total_likes'] or 0
    stats['total_dislikes'] = dish_stats['total_dislikes'] or 0

    # Đánh giá từ website: filter + paginate
    web_q = request.GET.get('web_q', '').strip()
    website_reviews_qs = stat_reviews.exclude(comment='').order_by('-updated_at')
    if web_q:
        website_reviews_qs = website_reviews_qs.filter(
            Q(comment__icontains=web_q) |
            Q(user__username__icontains=web_q) |
            Q(user__profile__full_name__icontains=web_q)
        )
    website_page = Paginator(website_reviews_qs, 20).get_page(request.GET.get('web_page'))

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
        review_count=Count('id')
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
            'has_review': bool(item and item['review_count'] > 0),
        })

        current_date += timedelta(days=1)

    context = {
        'selected_date': selected_date,
        'selected_date_str': selected_date.isoformat(),
        'can_review': can_review,
        'menu': menu,
        'form': form,
        'existing_review': existing_review,
        'existing_dish_reviews': existing_dish_reviews,
        'stats': stats,
        'website_page': website_page,
        'web_q': web_q,
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


@login_required
@require_POST
def ajax_review_dish(request):
    try:
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        evaluation = data.get('evaluation')
        date_str = data.get('date')
        
        if not dish_id or not evaluation or not date_str:
            return JsonResponse({'success': False, 'message': 'Thiếu dữ liệu.'})
            
        target_date = date.fromisoformat(date_str)
        if not can_review_date(target_date):
            return JsonResponse({'success': False, 'message': 'Hết thời gian đánh giá.'})
            
        meal_review, _ = MealReview.objects.get_or_create(
            date=target_date,
            user=request.user
        )
        
        DishReview.objects.update_or_create(
            meal_review=meal_review,
            dish_id=dish_id,
            defaults={'evaluation': evaluation}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


def public_review_view(request):
    today = date.today()
        
    menu = DailyMenu.objects.filter(
        date=today,
        status=DailyMenu.STATUS_APPROVED
    ).prefetch_related('items__dish').first()
    
    if not request.session.session_key:
        request.session.create()
        
    session_key = request.session.session_key
    
    existing_review = MealReview.objects.filter(
        date=today,
        session_key=session_key,
        user__isnull=True
    ).first()
    
    existing_dish_reviews = {}
    if existing_review:
        user_dish_reviews = DishReview.objects.filter(meal_review=existing_review)
        for dr in user_dish_reviews:
            existing_dish_reviews[dr.dish_id] = dr.evaluation
            
    if menu:
        for item in menu.items.all():
            item.user_evaluation = existing_dish_reviews.get(item.dish.id)
            
    context = {
        'menu': menu,
        'today': today,
        'can_review': can_review_date(today),
    }
    return render(request, 'reviews/public_review.html', context)


@require_POST
def ajax_public_review_dish(request):
    try:
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        evaluation = data.get('evaluation')
        
        if not dish_id or not evaluation:
            return JsonResponse({'success': False, 'message': 'Thiếu dữ liệu.'})
            
        today = date.today()
        if not can_review_date(today):
            return JsonResponse({'success': False, 'message': 'Hết thời gian đánh giá.'})
            
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
            
        meal_review, _ = MealReview.objects.get_or_create(
            date=today,
            user=None,
            session_key=session_key
        )
        
        DishReview.objects.update_or_create(
            meal_review=meal_review,
            dish_id=dish_id,
            defaults={'evaluation': evaluation}
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def qr_code_page(request):
    public_url = request.build_absolute_uri('/reviews/public/')
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={public_url}"
    context = {
        'public_url': public_url,
        'qr_image_url': qr_image_url
    }
    return render(request, 'reviews/qr_code.html', context)