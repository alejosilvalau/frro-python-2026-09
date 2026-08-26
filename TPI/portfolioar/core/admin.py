from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Sector, Broker, Stock


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'is_active')
    list_filter = ('is_active', 'is_staff')
    search_fields = ('first_name', 'last_name', 'email')
    ordering = ('first_name',)
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('phone', 'birthdate')}),
    )


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'primary')
    search_fields = ('name',)


@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ('name', 'link')
    search_fields = ('name',)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'company_name', 'sector')
    search_fields = ('ticker', 'company_name')
    list_filter = ('sector',)
