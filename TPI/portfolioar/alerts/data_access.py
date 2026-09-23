from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import TechnicalIndicator, AlertCondition, Alert, AlertTrigger
from core.data_access import get_user_by_id, get_stock_by_id


def get_all_indicators():
    return TechnicalIndicator.objects.all()


def get_indicator_by_id(indicator_id):
    return TechnicalIndicator.objects.get(id=indicator_id)


def create_indicator(name, description='', period=14):
    indicator = TechnicalIndicator(name=name, description=description, period=period)
    indicator.save()
    return indicator


def update_or_create_indicator(name, description='', period=14):
    indicator = TechnicalIndicator.objects.filter(name__iexact=name).first()
    if indicator is None:
        return create_indicator(name, description, period), True

    changed_fields = []
    if indicator.name != name:
        indicator.name = name
        changed_fields.append('name')
    if indicator.description != description:
        indicator.description = description
        changed_fields.append('description')
    if indicator.period != period:
        indicator.period = period
        changed_fields.append('period')
    if changed_fields:
        indicator.save(update_fields=changed_fields)
    return indicator, False


def get_all_conditions():
    return AlertCondition.objects.all()


def get_condition_by_id(condition_id):
    return AlertCondition.objects.get(id=condition_id)


def create_condition(indicator_id, operator, threshold_value):
    indicator = TechnicalIndicator.objects.get(id=indicator_id)
    condition = AlertCondition(indicator=indicator, operator=operator, threshold_value=threshold_value)
    condition.save()
    return condition


def get_alerts_by_user(user_id):
    return Alert.objects.filter(user_id=user_id)


def get_active_alerts():
    return (
        Alert.objects.filter(is_active=True)
        .select_related('stock')
        .prefetch_related('conditions__indicator')
    )


def get_alert_by_id(alert_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Alert, id=alert_id, user_id=user_id)
    return get_object_or_404(Alert, id=alert_id)


def get_conditions_by_alert(alert):
    return list(alert.conditions.all())


def create_alert(user_id, stock_id, name, is_active=True):
    user = get_user_by_id(user_id)
    stock = get_stock_by_id(stock_id)

    alert = Alert(user=user, stock=stock, name=name, is_active=is_active)
    alert.save()
    return alert


def update_alert(alert_id, name=None, is_active=None, stock_id=None):
    alert = Alert.objects.get(id=alert_id)
    if name is not None:
        alert.name = name
    if is_active is not None:
        alert.is_active = is_active
    if stock_id is not None:
        alert.stock = get_stock_by_id(stock_id)
    alert.save()
    return alert


def delete_alert(alert_id):
    Alert.objects.filter(id=alert_id).delete()


def add_condition_to_alert(alert_id, condition_id):
    alert = Alert.objects.get(id=alert_id)
    condition = AlertCondition.objects.get(id=condition_id)
    alert.conditions.add(condition)
    return alert


def remove_condition_from_alert(alert_id, condition_id):
    alert = Alert.objects.get(id=alert_id)
    condition = AlertCondition.objects.get(id=condition_id)
    alert.conditions.remove(condition)
    return alert


def get_triggers_by_alert(alert_id):
    return AlertTrigger.objects.filter(alert_id=alert_id).order_by('-trigger_datetime')


def create_trigger(alert_id, ai_recommendation=''):
    alert = Alert.objects.get(id=alert_id)
    trigger = AlertTrigger(alert=alert, ai_recommendation=ai_recommendation)
    trigger.save()
    return trigger


def create_trigger_if_cooldown_elapsed(alert_id, cooldown, ai_recommendation=''):
    """Crea un disparo solo si no hubo otro dentro del período indicado.

    El bloqueo de la alerta evita que dos ejecuciones concurrentes superen el
    cooldown al consultar el último disparo al mismo tiempo.
    """
    with transaction.atomic():
        alert = Alert.objects.select_for_update().get(id=alert_id)
        last_trigger = (
            AlertTrigger.objects.filter(alert_id=alert_id)
            .order_by('-trigger_datetime')
            .first()
        )
        now = timezone.now()
        if last_trigger and now < last_trigger.trigger_datetime + cooldown:
            return None

        return AlertTrigger.objects.create(
            alert=alert,
            ai_recommendation=ai_recommendation,
        )
