from django.shortcuts import get_object_or_404

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


def get_alert_by_id(alert_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Alert, id=alert_id, user_id=user_id)
    return get_object_or_404(Alert, id=alert_id)


def create_alert(user_id, stock_id, name, is_active=True):
    user = get_user_by_id(user_id)
    stock = get_stock_by_id(stock_id)

    alert = Alert(user=user, stock=stock, name=name, is_active=is_active)
    alert.save()
    return alert


def update_alert(alert_id, name=None, is_active=None):
    alert = Alert.objects.get(id=alert_id)
    if name is not None:
        alert.name = name
    if is_active is not None:
        alert.is_active = is_active
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
    return AlertTrigger.objects.filter(alert_id=alert_id)


def create_trigger(alert_id, ai_recommendation=''):
    alert = Alert.objects.get(id=alert_id)
    trigger = AlertTrigger(alert=alert, ai_recommendation=ai_recommendation)
    trigger.save()
    return trigger
