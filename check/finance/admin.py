from django.contrib import admin
from .models import DailyPurchase


@admin.register(DailyPurchase)
class DailyPurchaseAdmin(admin.ModelAdmin):
    list_display = ('date', 'actual_cost', 'created_by', 'created_at')
    list_filter = ('date',)
    search_fields = ('note',)