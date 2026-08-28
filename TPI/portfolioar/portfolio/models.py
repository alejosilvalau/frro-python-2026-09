from django.db import models
from django.conf import settings
from core.models import Stock, Broker


class Position(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='positions')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='positions')
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name='positions')
    amount = models.IntegerField()
    stock_price_local = models.DecimalField(max_digits=15, decimal_places=4)
    stock_price_usd = models.DecimalField(max_digits=15, decimal_places=4)
    purchased_at = models.DateTimeField()

    class Meta:
        db_table = 'position'
        verbose_name = 'posición'
        verbose_name_plural = 'posiciones'

    def __str__(self):
        return f"{self.stock.ticker} - {self.amount} unidades"


class Order(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='orders')
    amount = models.IntegerField()
    fulfill_datetime = models.DateTimeField()
    total_fees = models.DecimalField(max_digits=15, decimal_places=4)
    price_local = models.DecimalField(max_digits=15, decimal_places=4)
    price_usd = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        db_table = 'order'
        verbose_name = 'orden'
        verbose_name_plural = 'órdenes'

    def __str__(self):
        return f"Orden {self.id} - {self.position.stock.ticker}"


class CashPosition(models.Model):
    CURRENCY_CHOICES = [
        ('ARS', 'Pesos (ARS)'),
        ('USD', 'Dólares (USD)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cash_positions')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cash_position'
        verbose_name = 'liquidez'
        verbose_name_plural = 'liquidez'
        ordering = ['currency', '-created_at']

    def __str__(self):
        return f"{self.currency} {self.amount} - {self.description or 'Sin descripción'}"
