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
    inventory_list,
    inventory_add_manual,
    inventory_save_from_invoice,
    inventory_export,
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

    # QUẢN LÝ KHO
    path('inventory/', inventory_list, name='inventory_list'),
    path('inventory/add-manual/', inventory_add_manual, name='inventory_add_manual'),
    path('inventory/save-from-invoice/', inventory_save_from_invoice, name='inventory_save_from_invoice'),
    path('inventory/<int:pk>/export/', inventory_export, name='inventory_export'),
]