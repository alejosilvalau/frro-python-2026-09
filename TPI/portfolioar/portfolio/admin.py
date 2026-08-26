from django.contrib import admin
from .models import Position, Order


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('stock', 'user', 'broker', 'amount', 'stock_price_local', 'stock_price_usd', 'purchased_at')
    search_fields = ('stock__ticker', 'user__first_name', 'user__last_name')
    list_filter = ('broker', 'purchased_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('position', 'amount', 'fulfill_datetime', 'total_fees', 'price_local', 'price_usd')
    search_fields = ('position__stock__ticker',)
    list_filter = ('fulfill_datetime',)
