from django.contrib import admin

# Register your models here.
from .models import Dish, DailyMenu, DailyMenuItem


class DailyMenuItemInline(admin.TabularInline):
    model = DailyMenuItem
    extra = 1



@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'dish_type', 'portion_per_person', 'portion_unit', 'is_active')
    list_filter = ('dish_type', 'is_active')
    search_fields = ('name',)


@admin.register(DailyMenu)
class DailyMenuAdmin(admin.ModelAdmin):
    list_display = ('date', 'status', 'created_by', 'updated_at')
    list_filter = ('status', 'date')
    search_fields = ('note',)
    inlines = [DailyMenuItemInline]


@admin.register(DailyMenuItem)
class DailyMenuItemAdmin(admin.ModelAdmin):
    list_display = ('daily_menu', 'dish', 'sort_order')
    list_filter = ('dish__dish_type',)
    search_fields = ('dish__name',)