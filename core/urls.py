from django.urls import path
from .views import (
    dashboard,
    meal_price_list,
    meal_price_create,
    meal_price_update,
    nutrition_analysis_api
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('meal-prices/', meal_price_list, name='meal_price_list'),
    path('meal-prices/create/', meal_price_create, name='meal_price_create'),
    path('meal-prices/<int:pk>/edit/', meal_price_update, name='meal_price_update'),
    path(
    'nutrition-analysis/',
    nutrition_analysis_api,
    name='nutrition_analysis_api'
),
]