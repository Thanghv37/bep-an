from django.urls import path

from .views import (
    review_dashboard, review_delete, ajax_review_dish,
    public_review_view, ajax_public_review_dish, qr_code_page
)

urlpatterns = [
    path('reviews/', review_dashboard, name='review_dashboard'),
    path('reviews/<int:pk>/delete/', review_delete, name='review_delete'),
    path('reviews/ajax-dish/', ajax_review_dish, name='ajax_review_dish'),
    path('reviews/public/', public_review_view, name='public_review'),
    path('reviews/public/ajax-dish/', ajax_public_review_dish, name='ajax_public_review_dish'),
    path('reviews/qr-code/', qr_code_page, name='qr_code_page'),
]