from django.db import models
from django.conf import settings
from core.models import Stock


class TechnicalIndicator(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    period = models.IntegerField(default=14)

    class Meta:
        db_table = 'technical_indicator'
        verbose_name = 'indicador técnico'
        verbose_name_plural = 'indicadores técnicos'

    def __str__(self):
        return self.name


class AlertCondition(models.Model):
    indicator = models.ForeignKey(TechnicalIndicator, on_delete=models.CASCADE, related_name='conditions')
    operator = models.CharField(max_length=10)
    threshold_value = models.DecimalField(max_digits=15, decimal_places=4)

    class Meta:
        db_table = 'alert_condition'
        verbose_name = 'condición de alerta'
        verbose_name_plural = 'condiciones de alerta'

    def __str__(self):
        return f"{self.indicator.name} {self.operator} {self.threshold_value}"


class Alert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='alerts')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    conditions = models.ManyToManyField(AlertCondition, related_name='alerts')

    class Meta:
        db_table = 'alert'
        verbose_name = 'alerta'
        verbose_name_plural = 'alertas'

    def __str__(self):
        return f"{self.name} - {self.stock.ticker}"


class AlertTrigger(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='triggers')
    trigger_datetime = models.DateTimeField(auto_now_add=True)
    ai_recommendation = models.TextField(blank=True)

    class Meta:
        db_table = 'alert_trigger'
        verbose_name = 'disparo de alerta'
        verbose_name_plural = 'disparos de alerta'

    def __str__(self):
        return f"Trigger {self.id} - {self.alert.name}"
