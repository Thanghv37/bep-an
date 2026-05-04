from django.urls import path

from .views import review_dashboard, review_delete

urlpatterns = [
    path('reviews/', review_dashboard, name='review_dashboard'),
    path('reviews/<int:pk>/delete/', review_delete, name='review_delete'),
]