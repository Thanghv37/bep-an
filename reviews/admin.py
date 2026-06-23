from django.contrib import admin

from .models import ReviewInviteFeedback


@admin.register(ReviewInviteFeedback)
class ReviewInviteFeedbackAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'annoyed', 'user', 'session_key', 'updated_at')
    list_filter = ('annoyed', 'updated_at')
    search_fields = ('user__username', 'session_key')
