from django.urls import path
from .views import (
    dish_list, dish_create, dish_update, dish_delete,
    menu_list, menu_create, menu_update, menu_delete,
    approval_dashboard, approve_menu, approve_purchase, reject_purchase, reject_menu,
    approve_dish, reject_dish,export_ingredients_pdf, approve_extra_request, reject_extra_request,
    suggest_next_week_menu,
    apply_week_menu_draft,
    approve_all_dishes, approve_all_menus,
    approve_all_extra_requests, approve_all_purchases,
    menu_prep_confirm,
)

urlpatterns = [
    path('dishes/', dish_list, name='dish_list'),
    path('dishes/create/', dish_create, name='dish_create'),
    path('dishes/<int:pk>/edit/', dish_update, name='dish_update'),
    path('dishes/<int:pk>/delete/', dish_delete, name='dish_delete'),

    path('menus/', menu_list, name='menu_list'),
    path('menus/create/', menu_create, name='menu_create'),
    path('menus/<int:pk>/edit/', menu_update, name='menu_update'),
    path('menus/<int:pk>/delete/', menu_delete, name='menu_delete'),

    path('approvals/', approval_dashboard, name='approval_dashboard'),

    # MENU
    path('approvals/menus/<int:pk>/approve/', approve_menu, name='approve_menu'),
    path('approvals/menus/<int:pk>/reject/', reject_menu, name='reject_menu'),

    # PURCHASE
    path('approvals/purchases/<int:pk>/approve/', approve_purchase, name='approve_purchase'),
    path('approvals/purchases/<int:pk>/reject/', reject_purchase, name='reject_purchase'),

    # 🔥 DISH (MỚI)
    path('approvals/dishes/<int:pk>/approve/', approve_dish, name='approve_dish'),
    path('approvals/dishes/<int:pk>/reject/', reject_dish, name='reject_dish'),
    path('menus/export/pdf/', export_ingredients_pdf, name='export_ingredients_pdf'),
    
    path('approvals/extra-requests/<int:pk>/approve/', approve_extra_request, name='approve_extra_request'),
    path('approvals/extra-requests/<int:pk>/reject/', reject_extra_request, name='reject_extra_request'),

    # PHÊ DUYỆT TẤT CẢ theo từng loại
    path('approvals/dishes/approve-all/', approve_all_dishes, name='approve_all_dishes'),
    path('approvals/menus/approve-all/', approve_all_menus, name='approve_all_menus'),
    path('approvals/extra-requests/approve-all/', approve_all_extra_requests, name='approve_all_extra_requests'),
    path('approvals/purchases/approve-all/', approve_all_purchases, name='approve_all_purchases'),

    path('menus/api/suggest-next-week/', suggest_next_week_menu, name='suggest_next_week_menu'),
    path('menus/api/apply-week-draft/', apply_week_menu_draft, name='apply_week_menu_draft'),

    path('menus/<int:menu_id>/prep-confirm/', menu_prep_confirm, name='menu_prep_confirm'),
]