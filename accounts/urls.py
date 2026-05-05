from django.urls import path
from .views import user_profile, reset_user_password
from .views import user_list, user_create, user_update, user_delete,import_users, users_api, set_initial_password

urlpatterns = [
    path('users/', user_list, name='user_list'),
    path('users/create/', user_create, name='user_create'),
    path('users/<int:pk>/edit/', user_update, name='user_update'),
    path('users/<int:pk>/delete/', user_delete, name='user_delete'),
    path('users/import/', import_users, name='import_users'),
    path('profile/', user_profile, name='user_profile'),
    path('users/<int:pk>/reset-password/', reset_user_password, name='reset_user_password'),
    path('api/users/', users_api, name='users_api'),
    path('set-password/', set_initial_password, name='set_initial_password'),
]