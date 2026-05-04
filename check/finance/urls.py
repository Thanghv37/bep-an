from django.urls import path
from .views import purchase_list, purchase_create, purchase_update
from .views import purchase_list, purchase_create, purchase_update, purchase_ingredients_by_date
urlpatterns = [
    path('purchases/', purchase_list, name='purchase_list'),
    path('purchases/create/', purchase_create, name='purchase_create'),
    path('purchases/<int:pk>/edit/', purchase_update, name='purchase_update'),
    path('purchases/ingredients/', purchase_ingredients_by_date, name='purchase_ingredients_by_date'),
]