from django.contrib import admin

from .models import RecognitionHeartbeat, CameraStatusLog


@admin.register(RecognitionHeartbeat)
class RecognitionHeartbeatAdmin(admin.ModelAdmin):
    list_display = ('camera_id', 'last_heartbeat_at')
    search_fields = ('camera_id',)


@admin.register(CameraStatusLog)
class CameraStatusLogAdmin(admin.ModelAdmin):
    list_display = ('camera_id', 'status', 'changed_at')
    list_filter = ('status', 'camera_id')
    search_fields = ('camera_id',)
    date_hierarchy = 'changed_at'
