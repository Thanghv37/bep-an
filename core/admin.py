from django.contrib import admin

from .models import RecognitionHeartbeat, CameraStatusLog, AttendanceCapture


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


@admin.register(AttendanceCapture)
class AttendanceCaptureAdmin(admin.ModelAdmin):
    list_display = ('employee_code', 'camera_id', 'status', 'score', 'scan_time')
    list_filter = ('status', 'camera_id')
    search_fields = ('employee_code',)
    date_hierarchy = 'scan_time'
