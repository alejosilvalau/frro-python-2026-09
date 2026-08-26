from django.contrib import admin
from .models import TechnicalIndicator, AlertCondition, Alert, AlertTrigger


@admin.register(TechnicalIndicator)
class TechnicalIndicatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'period')
    search_fields = ('name',)


@admin.register(AlertCondition)
class AlertConditionAdmin(admin.ModelAdmin):
    list_display = ('indicator', 'operator', 'threshold_value')
    search_fields = ('indicator__name',)
    list_filter = ('operator',)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('name', 'stock', 'user', 'is_active', 'created_at')
    search_fields = ('name', 'stock__ticker', 'user__first_name', 'user__last_name')
    list_filter = ('is_active', 'created_at')


@admin.register(AlertTrigger)
class AlertTriggerAdmin(admin.ModelAdmin):
    list_display = ('alert', 'trigger_datetime', 'ai_recommendation')
    search_fields = ('alert__name',)
    list_filter = ('trigger_datetime',)
