from django.test import TestCase

from core.models import User, Sector, Stock
from alerts.models import TechnicalIndicator, AlertCondition, Alert, AlertTrigger
from alerts.business import AlertManager


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
