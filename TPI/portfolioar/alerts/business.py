from decimal import Decimal
from .data_access import (
    get_all_indicators, get_indicator_by_id, create_indicator,
    get_all_conditions, get_condition_by_id, create_condition,
    get_alerts_by_user, get_alert_by_id, create_alert,
    update_alert, delete_alert, add_condition_to_alert,
    remove_condition_from_alert, get_triggers_by_alert, create_trigger
)


class IndicatorManager:
    def get_all(self):
        return get_all_indicators()

    def get_by_id(self, indicator_id):
        return get_indicator_by_id(indicator_id)

    def create(self, name, description='', period=14):
        return create_indicator(name, description, period)


class ConditionManager:
    def get_all(self):
        return get_all_conditions()

    def get_by_id(self, condition_id):
        return get_condition_by_id(condition_id)

    def create(self, indicator_id, operator, threshold_value):
        valid_operators = ['>', '<', '>=', '<=', '==', '!=']
        if operator not in valid_operators:
            raise ValueError(f"Operador inválido. Use: {', '.join(valid_operators)}")

        if threshold_value < 0:
            raise ValueError("El valor umbral debe ser mayor o igual a 0")

        return create_condition(indicator_id, operator, threshold_value)


class AlertManager:
    def get_user_alerts(self, user_id):
        return get_alerts_by_user(user_id)

    def get_alert(self, alert_id, user_id=None):
        return get_alert_by_id(alert_id, user_id)

    def create_alert(self, user_id, stock_id, name, is_active=True):
        if not name:
            raise ValueError("El nombre es obligatorio")

        return create_alert(user_id, stock_id, name, is_active)

    def update_alert(self, alert_id, name=None, is_active=None):
        return update_alert(alert_id, name, is_active)

    def delete_alert(self, alert_id):
        delete_alert(alert_id)

    def add_condition(self, alert_id, condition_id):
        return add_condition_to_alert(alert_id, condition_id)

    def remove_condition(self, alert_id, condition_id):
        return remove_condition_from_alert(alert_id, condition_id)

    def evaluate_alert(self, alert, current_values):
        for condition in alert.conditions.all():
            indicator_name = condition.indicator.name.lower()
            if indicator_name not in current_values:
                continue

            current_value = Decimal(str(current_values[indicator_name]))
            threshold = condition.threshold_value
            operator = condition.operator

            if operator == '>' and not (current_value > threshold):
                return False
            elif operator == '<' and not (current_value < threshold):
                return False
            elif operator == '>=' and not (current_value >= threshold):
                return False
            elif operator == '<=' and not (current_value <= threshold):
                return False
            elif operator == '==' and not (current_value == threshold):
                return False
            elif operator == '!=' and not (current_value != threshold):
                return False

        return True

    def trigger_alert(self, alert, ai_recommendation=''):
        return create_trigger(alert.id, ai_recommendation)
