from django.contrib import admin
from .models import Position, Lot, Sale, SaleLot


class LotInline(admin.TabularInline):
    model = Lot
    extra = 0


class SaleInline(admin.TabularInline):
    model = Sale
    extra = 0


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('stock', 'user', 'broker', 'status', 'opened_at')
    search_fields = ('stock__ticker', 'user__first_name', 'user__last_name')
    list_filter = ('broker', 'status')
    inlines = [LotInline, SaleInline]


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ('position', 'amount', 'purchase_currency', 'price_local', 'price_usd', 'purchased_at', 'fees')
    search_fields = ('position__stock__ticker',)
    list_filter = ('purchase_currency', 'purchased_at')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('position', 'amount', 'sell_currency', 'price_local', 'price_usd', 'sold_at', 'realized_pnl_ars', 'realized_pnl_usd')
    search_fields = ('position__stock__ticker',)
    list_filter = ('sell_currency', 'sold_at')


@admin.register(SaleLot)
class SaleLotAdmin(admin.ModelAdmin):
    list_display = ('sale', 'lot', 'amount_consumed', 'cost_price_local', 'cost_price_usd')
