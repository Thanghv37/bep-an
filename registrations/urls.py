from django.urls import path

from .views import (
    registration_list,
    registration_import,
    registration_create,
    registrations_by_date_api,
    registration_delete,
)

urlpatterns = [
    path('', registration_list, name='registration_list'),
    path('import/', registration_import, name='registration_import'),
    path('create/', registration_create, name='registration_create'),
    path('api/by-date/', registrations_by_date_api, name='registrations_by_date_api'),
    path('<int:pk>/delete/', registration_delete, name='registration_delete'),
]