from django.urls import path

from .views import (
    registration_list,
    registration_import,
    registration_create,
)

urlpatterns = [
    path('', registration_list, name='registration_list'),
    path('import/', registration_import, name='registration_import'),
    path('create/', registration_create, name='registration_create'),
]