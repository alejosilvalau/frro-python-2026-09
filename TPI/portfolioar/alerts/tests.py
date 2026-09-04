from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Sector, Stock
from alerts.models import TechnicalIndicator, AlertCondition, Alert, AlertTrigger
from alerts.business import AlertManager, ConditionManager


class TechnicalIndicatorModelTest(TestCase):
    def setUp(self):
        self.indicator = TechnicalIndicator.objects.create(
            name='RSI',
            description='Relative Strength Index',
            period=14
        )

    def test_indicator_creation(self):
        self.assertEqual(self.indicator.name, 'RSI')
        self.assertEqual(self.indicator.description, 'Relative Strength Index')
        self.assertEqual(self.indicator.period, 14)

    def test_indicator_str(self):
        self.assertEqual(str(self.indicator), 'RSI')


class AlertConditionModelTest(TestCase):
    def setUp(self):
        self.indicator = TechnicalIndicator.objects.create(
            name='RSI',
            description='Relative Strength Index',
            period=14
        )
        self.condition = AlertCondition.objects.create(
            indicator=self.indicator,
            operator='>',
            threshold_value=70
        )

    def test_condition_creation(self):
        self.assertEqual(self.condition.indicator, self.indicator)
        self.assertEqual(self.condition.operator, '>')
        self.assertEqual(self.condition.threshold_value, 70)

    def test_condition_str(self):
        self.assertEqual(str(self.condition), 'RSI > 70')


class AlertModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            first_name='Juan',
            last_name='Pérez',
            email='juan@example.com',
            password='testpass123'
        )
        self.sector = Sector.objects.create(name='Technology')
        self.stock = Stock.objects.create(
            ticker='AAPL',
            company_name='Apple Inc.',
            sector=self.sector
        )
        self.alert = Alert.objects.create(
            user=self.user,
            stock=self.stock,
            name='RSI Alert',
            is_active=True
        )

    def test_alert_creation(self):
        self.assertEqual(self.alert.user, self.user)
        self.assertEqual(self.alert.stock, self.stock)
        self.assertEqual(self.alert.name, 'RSI Alert')
        self.assertTrue(self.alert.is_active)

    def test_alert_str(self):
        self.assertEqual(str(self.alert), 'RSI Alert - AAPL')


class AlertTriggerModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            first_name='Juan',
            last_name='Pérez',
            email='juan@example.com',
            password='testpass123'
        )
        self.sector = Sector.objects.create(name='Technology')
        self.stock = Stock.objects.create(
            ticker='AAPL',
            company_name='Apple Inc.',
            sector=self.sector
        )
        self.alert = Alert.objects.create(
            user=self.user,
            stock=self.stock,
            name='RSI Alert',
            is_active=True
        )
        self.trigger = AlertTrigger.objects.create(
            alert=self.alert,
            ai_recommendation='RSI is above 70, consider selling'
        )

    def test_trigger_creation(self):
        self.assertEqual(self.trigger.alert, self.alert)
        self.assertEqual(self.trigger.ai_recommendation, 'RSI is above 70, consider selling')

    def test_trigger_str(self):
        self.assertEqual(str(self.trigger), f'Trigger {self.trigger.id} - RSI Alert')


class AlertManagerTest(TestCase):
    def setUp(self):
        self.alert_manager = AlertManager()

        self.user = User.objects.create_user(
            first_name='Juan',
            last_name='Pérez',
            email='juan@example.com',
            password='testpass123'
        )
        self.sector = Sector.objects.create(name='Technology')
        self.stock = Stock.objects.create(
            ticker='AAPL',
            company_name='Apple Inc.',
            sector=self.sector
        )
        self.indicator = TechnicalIndicator.objects.create(
            name='RSI',
            description='Relative Strength Index',
            period=14
        )
        self.condition = AlertCondition.objects.create(
            indicator=self.indicator,
            operator='>',
            threshold_value=70
        )
        self.alert = Alert.objects.create(
            user=self.user,
            stock=self.stock,
            name='RSI Alert',
            is_active=True
        )

    def test_create_alert(self):
        alert = self.alert_manager.create_alert(
            self.user.id, self.stock.id, 'Test Alert', True
        )
        self.assertEqual(alert.name, 'Test Alert')
        self.assertTrue(alert.is_active)

    def test_create_alert_validation(self):
        with self.assertRaises(ValueError):
            self.alert_manager.create_alert(
                self.user.id, self.stock.id, '', True
            )

    def test_evaluate_alert(self):
        self.alert.conditions.add(self.condition)

        current_values = {'rsi': 75}
        result = self.alert_manager.evaluate_alert(self.alert, current_values)
        self.assertTrue(result)

        current_values = {'rsi': 65}
        result = self.alert_manager.evaluate_alert(self.alert, current_values)
        self.assertFalse(result)

    def test_get_user_alerts(self):
        alerts = self.alert_manager.get_user_alerts(self.user.id)
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.first(), self.alert)

    def test_evaluate_alert_and_logic_across_multiple_conditions(self):
        """RN06: la alerta solo se dispara si TODAS las condiciones se cumplen (AND)."""
        macd_indicator = TechnicalIndicator.objects.create(name='MACD', period=12)
        macd_condition = AlertCondition.objects.create(
            indicator=macd_indicator, operator='<', threshold_value=0
        )
        self.alert.conditions.add(self.condition, macd_condition)

        # Ambas condiciones se cumplen -> dispara
        self.assertTrue(self.alert_manager.evaluate_alert(self.alert, {'rsi': 75, 'macd': -1}))

        # Una condición no se cumple -> no dispara, aunque la otra sí
        self.assertFalse(self.alert_manager.evaluate_alert(self.alert, {'rsi': 75, 'macd': 1}))


class ConditionManagerTest(TestCase):
    """RN05: los operadores de condición de alerta deben ser válidos."""

    def setUp(self):
        self.condition_manager = ConditionManager()
        self.indicator = TechnicalIndicator.objects.create(name='RSI', period=14)

    def test_create_valid_condition(self):
        condition = self.condition_manager.create(self.indicator.id, '>', 70)
        self.assertEqual(condition.operator, '>')

    def test_create_invalid_operator_raises(self):
        with self.assertRaises(ValueError):
            self.condition_manager.create(self.indicator.id, '<>', 70)

    def test_create_negative_threshold_raises(self):
        with self.assertRaises(ValueError):
            self.condition_manager.create(self.indicator.id, '>', -5)


class AlertViewsTest(TestCase):
    """CU03 - Configurar una alerta técnica."""

    def setUp(self):
        self.user = User.objects.create_user(
            first_name='Juan', last_name='Pérez', email='juan@example.com', password='testpass123'
        )
        self.sector = Sector.objects.create(name='Technology')
        self.stock = Stock.objects.create(ticker='AAPL', company_name='Apple Inc.', sector=self.sector)
        self.indicator = TechnicalIndicator.objects.create(name='RSI', period=14)
        self.condition = AlertCondition.objects.create(
            indicator=self.indicator, operator='>', threshold_value=70
        )

        self.client = Client()
        self.client.force_login(self.user)

    def test_alert_list_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('alerts:alert_list'))
        self.assertEqual(resp.status_code, 302)

    def test_alert_create_get(self):
        resp = self.client.get(reverse('alerts:alert_create'))
        self.assertEqual(resp.status_code, 200)

    def test_alert_create_post_success(self):
        resp = self.client.post(reverse('alerts:alert_create'), {
            'stock_id': self.stock.id,
            'name': 'Mi alerta RSI',
            'is_active': 'on',
        })
        self.assertRedirects(resp, reverse('alerts:alert_list'))
        self.assertEqual(Alert.objects.filter(user=self.user).count(), 1)

    def test_alert_create_post_missing_name_shows_error(self):
        resp = self.client.post(reverse('alerts:alert_create'), {
            'stock_id': self.stock.id,
            'name': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
        self.assertEqual(Alert.objects.filter(user=self.user).count(), 0)

    def test_alert_detail_shows_available_conditions(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.get(reverse('alerts:alert_detail', args=[alert.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.condition, resp.context['conditions'])

    def test_alert_add_condition_attaches_existing_condition(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.post(reverse('alerts:alert_add_condition', args=[alert.id]), {
            'condition_id': self.condition.id,
        })
        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        self.assertIn(self.condition, alert.conditions.all())

    def test_alert_remove_condition(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        alert.conditions.add(self.condition)
        resp = self.client.get(reverse('alerts:alert_remove_condition', args=[alert.id, self.condition.id]))
        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        self.assertNotIn(self.condition, alert.conditions.all())

    def test_alert_delete(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.get(reverse('alerts:alert_delete', args=[alert.id]))
        self.assertRedirects(resp, reverse('alerts:alert_list'))
        self.assertFalse(Alert.objects.filter(id=alert.id).exists())

    def test_other_users_alert_returns_404(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        other_user = User.objects.create_user(
            first_name='Otro', last_name='Usuario', email='otro@example.com', password='testpass123'
        )
        other_client = Client()
        other_client.force_login(other_user)
        resp = other_client.get(reverse('alerts:alert_detail', args=[alert.id]))
        self.assertEqual(resp.status_code, 404)
