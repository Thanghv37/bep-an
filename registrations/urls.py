from django.urls import path

from .views import (
    registration_list,
    registration_import,
    registration_create,
    registration_options,
    registrations_by_date_api,
    registration_delete,
    delete_all_registrations,
    registration_participation,
    export_participation_excel,
    participation_send_netchat,
    participation_settings,
    send_meal_notifications,
    get_notification_logs_api,
)

urlpatterns = [
    path('', registration_list, name='registration_list'),
    path('import/', registration_import, name='registration_import'),
    path('create/', registration_create, name='registration_create'),
    path('options/', registration_options, name='registration_options'),
    path('api/by-date/', registrations_by_date_api, name='registrations_by_date_api'),
    path('<int:pk>/delete/', registration_delete, name='registration_delete'),
    path(
        'delete-all/',
        delete_all_registrations,
        name='delete_all_registrations'
    ),
    path('participation/', registration_participation, name='registration_participation'),
    path('participation/export/', export_participation_excel, name='export_participation_excel'),
    path('participation/send-netchat/', participation_send_netchat, name='participation_send_netchat'),
    path('participation/settings/', participation_settings, name='participation_settings'),
    path('api/send-notifications/', send_meal_notifications, name='send_meal_notifications'),
    path('api/notification-logs/', get_notification_logs_api, name='get_notification_logs_api'),
]