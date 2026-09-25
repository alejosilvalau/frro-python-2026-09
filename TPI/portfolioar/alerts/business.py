from datetime import timedelta
from decimal import Decimal
import re
import unicodedata

from django.db import transaction

from portfolio.business import PortfolioManager

from .data_access import (
    get_all_indicators, get_indicator_by_id, create_indicator,
    update_or_create_indicator,
    get_all_conditions, get_condition_by_id, create_condition,
    get_alerts_by_user, get_active_alerts, get_alert_by_id, create_alert,
    update_alert, delete_alert, add_condition_to_alert,
    remove_condition_from_alert, get_conditions_by_alert,
    get_triggers_by_alert, create_trigger_if_cooldown_elapsed
)


DEFAULT_INDICATORS = [
    ('RSI', 'Índice de fuerza relativa', 14),
    ('MACD', 'Convergencia/divergencia de medias móviles', 26),
    ('SMA 20', 'Media móvil simple de 20 ruedas', 20),
    ('SMA 50', 'Media móvil simple de 50 ruedas', 50),
    ('EMA 30', 'Media móvil exponencial de 30 ruedas', 30),
    ('Volumen relativo', 'Volumen actual respecto del promedio', 20),
    ('Volatilidad', 'Volatilidad anualizada de los retornos', 20),
]

ALERT_COOLDOWN = timedelta(minutes=15)


def _indicator_key(name):
    normalized = unicodedata.normalize('NFKD', name)
    without_accents = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '_', without_accents.lower()).strip('_')


class IndicatorManager:
    def get_all(self):
        return get_all_indicators()

    def get_by_id(self, indicator_id):
        return get_indicator_by_id(indicator_id)

    def create(self, name, description='', period=14):
        return create_indicator(name, description, period)

    def seed_defaults(self):
        created = 0
        for name, description, period in DEFAULT_INDICATORS:
            _, was_created = update_or_create_indicator(name, description, period)
            created += int(was_created)
        return {'created': created, 'existing': len(DEFAULT_INDICATORS) - created}


class ConditionManager:
    def get_all(self):
        return get_all_conditions()

    def get_by_id(self, condition_id):
        return get_condition_by_id(condition_id)

    def create(self, indicator_id, operator, threshold_value):
        valid_operators = ['>', '<', '>=', '<=', '==', '!=']
        if operator not in valid_operators:
            raise ValueError(f"Operador inválido. Use: {', '.join(valid_operators)}")

        return create_condition(indicator_id, operator, threshold_value)


class AlertManager:
    def get_user_alerts(self, user_id):
        return get_alerts_by_user(user_id)

    def get_alert(self, alert_id, user_id=None):
        return get_alert_by_id(alert_id, user_id)

    def get_alert_conditions(self, alert):
        return get_conditions_by_alert(alert)

    def get_alert_triggers(self, alert_id):
        return get_triggers_by_alert(alert_id)

    def create_alert(self, user_id, stock_id, name, is_active=True):
        if not name:
            raise ValueError("El nombre es obligatorio")

        return create_alert(user_id, stock_id, name, is_active)

    def create_alert_with_condition(
        self, user_id, stock_id, name, indicator_id, operator, threshold_value, is_active=True
    ):
        """Crea una alerta utilizable: nunca persiste el contenedor sin su primera regla."""
        with transaction.atomic():
            alert = self.create_alert(user_id, stock_id, name, is_active)
            condition = ConditionManager().create(indicator_id, operator, threshold_value)
            self.add_condition(alert.id, condition.id)
        return alert

    def update_alert(self, alert_id, name=None, is_active=None, stock_id=None):
        if not name:
            raise ValueError("El nombre es obligatorio")
        return update_alert(alert_id, name, is_active, stock_id)

    def delete_alert(self, alert_id):
        delete_alert(alert_id)

    def add_condition(self, alert_id, condition_id):
        return add_condition_to_alert(alert_id, condition_id)

    def create_and_add_condition(self, alert_id, indicator_id, operator, threshold_value):
        """Agrega una regla nueva sin dejar una condición suelta si la asociación falla."""
        with transaction.atomic():
            condition = ConditionManager().create(indicator_id, operator, threshold_value)
            self.add_condition(alert_id, condition.id)
        return condition

    def remove_condition(self, alert_id, condition_id):
        alert = get_alert_by_id(alert_id)
        if len(get_conditions_by_alert(alert)) <= 1:
            raise ValueError("Una alerta debe conservar al menos una condición")
        return remove_condition_from_alert(alert_id, condition_id)

    def evaluate_alert(self, alert, current_values, conditions=None):
        conditions = conditions if conditions is not None else get_conditions_by_alert(alert)
        if not conditions:
            return False

        for condition in conditions:
            indicator_name = _indicator_key(condition.indicator.name)
            if indicator_name not in current_values:
                return False

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

    def trigger_alert(self, alert, ai_recommendation='', cooldown=ALERT_COOLDOWN):
        return create_trigger_if_cooldown_elapsed(alert.id, cooldown, ai_recommendation)

    def evaluate_active_alerts(self):
        alerts = list(get_active_alerts())
        values_by_stock = {}
        stats = {'evaluated': 0, 'triggered': 0, 'cooldown': 0, 'skipped': 0, 'errors': 0}
        portfolio_manager = PortfolioManager()

        alert_entries = []
        required_by_stock = {}
        for alert in alerts:
            conditions = get_conditions_by_alert(alert)
            if not conditions:
                stats['skipped'] += 1
                continue
            alert_entries.append((alert, conditions))
            required_by_stock.setdefault(alert.stock_id, set()).update(
                _indicator_key(condition.indicator.name) for condition in conditions
            )

        for alert, conditions in alert_entries:
            if alert.stock_id not in values_by_stock:
                try:
                    values_by_stock[alert.stock_id] = portfolio_manager.get_alert_indicator_values(
                        alert.stock, required_by_stock[alert.stock_id]
                    )
                except Exception:
                    values_by_stock[alert.stock_id] = {}
                    stats['errors'] += 1

            current_values = values_by_stock[alert.stock_id]
            if any(_indicator_key(condition.indicator.name) not in current_values for condition in conditions):
                stats['skipped'] += 1
                continue

            stats['evaluated'] += 1
            if self.evaluate_alert(alert, current_values, conditions):
                trigger = self.trigger_alert(alert)
                if trigger is None:
                    stats['cooldown'] += 1
                else:
                    stats['triggered'] += 1

        return stats
