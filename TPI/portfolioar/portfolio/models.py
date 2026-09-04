from django.db import models
from django.conf import settings
from core.models import Stock, Broker


class Position(models.Model):
    STATUS_CHOICES = [('open', 'Abierta'), ('closed', 'Cerrada')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='positions')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='positions')
    broker = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name='positions')
    status = models.CharField(max_length=6, choices=STATUS_CHOICES, default='open')
    opened_at = models.DateTimeField()

    class Meta:
        db_table = 'position'
        verbose_name = 'posición'
        verbose_name_plural = 'posiciones'
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.stock.ticker} ({self.get_status_display()})"


class Lot(models.Model):
    CURRENCY_CHOICES = [('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')]

    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='lots')
    amount = models.IntegerField()
    price_local = models.DecimalField(max_digits=15, decimal_places=4)
    price_usd = models.DecimalField(max_digits=15, decimal_places=4)
    purchased_at = models.DateTimeField()
    purchase_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='ARS')
    fees = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    class Meta:
        db_table = 'lot'
        verbose_name = 'lote'
        verbose_name_plural = 'lotes'
        ordering = ['purchased_at', 'id']

    def __str__(self):
        return f"Lote {self.id} - {self.position.stock.ticker} x{self.amount}"


class Sale(models.Model):
    CURRENCY_CHOICES = [('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')]

    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='sales')
    amount = models.IntegerField()
    price_local = models.DecimalField(max_digits=15, decimal_places=4)
    price_usd = models.DecimalField(max_digits=15, decimal_places=4)
    sold_at = models.DateTimeField()
    sell_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='ARS')
    realized_pnl_ars = models.DecimalField(max_digits=18, decimal_places=4)
    realized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = 'sale'
        verbose_name = 'venta'
        verbose_name_plural = 'ventas'
        ordering = ['-sold_at', '-id']

    def __str__(self):
        return f"Venta {self.id} - {self.position.stock.ticker} x{self.amount}"


class SaleLot(models.Model):
    """Traza de auditoría FIFO: qué lotes consumió cada venta."""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='consumed_lots')
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name='sale_lots')
    amount_consumed = models.IntegerField()
    cost_price_local = models.DecimalField(max_digits=15, decimal_places=4)
    cost_price_usd = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        db_table = 'sale_lot'
        verbose_name = 'lote de venta'
        verbose_name_plural = 'lotes de venta'

    def __str__(self):
        return f"SaleLot sale={self.sale_id} lot={self.lot_id} qty={self.amount_consumed}"


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


class CashTransaction(models.Model):
    TIPO_CHOICES = [('compra', 'Compra'), ('recupero', 'Recupero')]
    CURRENCY_CHOICES = [('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cash_transactions')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions')
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions')
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_transactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cash_transaction'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tipo} {self.currency} {self.amount}"
