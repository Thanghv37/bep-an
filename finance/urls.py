from django.urls import path
from .views import (
    purchase_list,
    purchase_create,
    purchase_update,
    purchase_ingredients_by_date,
    extra_request_create,
    extra_request_by_date,
    extra_request_list,
    scan_bill_ajax,
)

urlpatterns = [
    path('purchases/', purchase_list, name='purchase_list'),
    path('purchases/create/', purchase_create, name='purchase_create'),
    path('purchases/<int:pk>/edit/', purchase_update, name='purchase_update'),
    path('purchases/ingredients/', purchase_ingredients_by_date, name='purchase_ingredients_by_date'),
    path('purchases/scan-bill/', scan_bill_ajax, name='scan_bill_ajax'),

    path('extra-requests/', extra_request_list, name='extra_request_list'),
    path('extra-requests/create/', extra_request_create, name='extra_request_create'),
    path('extra-requests/by-date/', extra_request_by_date, name='extra_request_by_date'),
]