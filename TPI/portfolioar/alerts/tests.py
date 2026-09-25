from io import StringIO
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

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

    def test_database_rejects_invalid_operator(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AlertCondition.objects.create(
                    indicator=self.indicator,
                    operator='invalido',
                    threshold_value=70,
                )


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

    def test_create_alert_with_initial_condition(self):
        alert = self.alert_manager.create_alert_with_condition(
            self.user.id, self.stock.id, 'Alerta completa', self.indicator.id, '>=', 65, True
        )

        self.assertEqual(alert.conditions.count(), 1)
        self.assertEqual(alert.conditions.first().indicator, self.indicator)

    def test_create_alert_with_invalid_condition_rolls_back(self):
        alerts_before = Alert.objects.count()
        conditions_before = AlertCondition.objects.count()

        with self.assertRaises(ValueError):
            self.alert_manager.create_alert_with_condition(
                self.user.id, self.stock.id, 'Alerta inválida', self.indicator.id, '<>', 65, True
            )

        self.assertEqual(Alert.objects.count(), alerts_before)
        self.assertEqual(AlertCondition.objects.count(), conditions_before)

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

    def test_macd_negative_threshold_can_be_created_and_evaluated(self):
        macd_indicator = TechnicalIndicator.objects.create(name='MACD', period=12)
        macd_condition = ConditionManager().create(macd_indicator.id, '<', -1)
        self.alert.conditions.add(macd_condition)

        self.assertEqual(macd_condition.threshold_value, -1)
        self.assertTrue(self.alert_manager.evaluate_alert(self.alert, {'macd': -2}))
        self.assertFalse(self.alert_manager.evaluate_alert(self.alert, {'macd': 0}))

    def test_alert_without_conditions_does_not_trigger(self):
        self.assertFalse(self.alert_manager.evaluate_alert(self.alert, {'rsi': 75}))

    def test_missing_indicator_value_does_not_trigger(self):
        self.alert.conditions.add(self.condition)
        self.assertFalse(self.alert_manager.evaluate_alert(self.alert, {}))

    def test_indicator_names_are_normalized(self):
        sma = TechnicalIndicator.objects.create(name='SMA 20', period=20)
        condition = AlertCondition.objects.create(indicator=sma, operator='>', threshold_value=100)
        self.alert.conditions.add(condition)
        self.assertTrue(self.alert_manager.evaluate_alert(self.alert, {'sma_20': 120}))

    @patch('alerts.business.PortfolioManager.get_alert_indicator_values', return_value={'rsi': 75})
    def test_evaluate_active_alerts_registers_only_matching_active_alerts(self, mock_values):
        self.alert.conditions.add(self.condition)
        inactive = Alert.objects.create(
            user=self.user, stock=self.stock, name='Inactiva', is_active=False
        )
        inactive.conditions.add(self.condition)

        stats = self.alert_manager.evaluate_active_alerts()

        self.assertEqual(stats['evaluated'], 1)
        self.assertEqual(stats['triggered'], 1)
        self.assertEqual(stats['skipped'], 0)
        self.assertEqual(AlertTrigger.objects.filter(alert=self.alert).count(), 1)
        self.assertFalse(AlertTrigger.objects.filter(alert=inactive).exists())
        mock_values.assert_called_once_with(self.stock, {'rsi'})

    @patch('alerts.business.PortfolioManager.get_alert_indicator_values', return_value={})
    def test_evaluate_active_alerts_skips_missing_market_data(self, mock_values):
        self.alert.conditions.add(self.condition)

        stats = self.alert_manager.evaluate_active_alerts()

        self.assertEqual(stats['evaluated'], 0)
        self.assertEqual(stats['triggered'], 0)
        self.assertEqual(stats['skipped'], 1)
        self.assertFalse(AlertTrigger.objects.exists())

    @patch('alerts.business.PortfolioManager.get_alert_indicator_values', return_value={'rsi': 75})
    def test_evaluate_active_alerts_applies_fifteen_minute_cooldown(self, mock_values):
        self.alert.conditions.add(self.condition)

        first_stats = self.alert_manager.evaluate_active_alerts()
        second_stats = self.alert_manager.evaluate_active_alerts()

        self.assertEqual(first_stats['triggered'], 1)
        self.assertEqual(second_stats['triggered'], 0)
        self.assertEqual(second_stats['cooldown'], 1)
        self.assertEqual(AlertTrigger.objects.filter(alert=self.alert).count(), 1)
        self.assertEqual(mock_values.call_count, 2)

    @patch('alerts.business.PortfolioManager.get_alert_indicator_values', return_value={'rsi': 75})
    def test_evaluate_active_alerts_retriggers_after_cooldown(self, mock_values):
        self.alert.conditions.add(self.condition)
        trigger = AlertTrigger.objects.create(alert=self.alert)
        AlertTrigger.objects.filter(id=trigger.id).update(
            trigger_datetime=timezone.now() - timedelta(minutes=16)
        )

        stats = self.alert_manager.evaluate_active_alerts()

        self.assertEqual(stats['triggered'], 1)
        self.assertEqual(AlertTrigger.objects.filter(alert=self.alert).count(), 2)


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

    def test_create_negative_threshold(self):
        condition = self.condition_manager.create(self.indicator.id, '>', -5)
        self.assertEqual(condition.threshold_value, -5)


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
        self.assertContains(resp, 'stock_type_filter')
        self.assertContains(resp, 'new TomSelect(stockSelect')

    def test_alert_create_post_success(self):
        resp = self.client.post(reverse('alerts:alert_create'), {
            'stock_id': self.stock.id,
            'name': 'Mi alerta RSI',
            'is_active': 'on',
            'indicator_id': self.indicator.id,
            'operator': '>',
            'threshold_value': '70',
        })
        alert = Alert.objects.get(user=self.user)
        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        self.assertEqual(Alert.objects.filter(user=self.user).count(), 1)
        self.assertEqual(alert.conditions.count(), 1)

    def test_alert_create_post_missing_name_shows_error(self):
        resp = self.client.post(reverse('alerts:alert_create'), {
            'stock_id': self.stock.id,
            'name': '',
            'indicator_id': self.indicator.id,
            'operator': '>',
            'threshold_value': '70',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
        self.assertEqual(Alert.objects.filter(user=self.user).count(), 0)

    def test_alert_update_persists_selected_stock(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        other_stock = Stock.objects.create(
            ticker='MSFT', company_name='Microsoft', sector=self.sector
        )

        resp = self.client.post(reverse('alerts:alert_update', args=[alert.id]), {
            'stock_id': other_stock.id,
            'name': 'Alerta MSFT',
            'is_active': 'on',
        })

        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        alert.refresh_from_db()
        self.assertEqual(alert.stock, other_stock)
        self.assertEqual(alert.name, 'Alerta MSFT')

    def test_alert_detail_shows_available_indicators_for_new_conditions(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.get(reverse('alerts:alert_detail', args=[alert.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.indicator, resp.context['indicators'])

    def test_alert_detail_shows_trigger_history(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        trigger = AlertTrigger.objects.create(alert=alert)
        resp = self.client.get(reverse('alerts:alert_detail', args=[alert.id]))
        self.assertContains(resp, 'Historial de Disparos')
        self.assertIn(trigger, resp.context['triggers'])

    def test_alert_add_condition_creates_and_attaches_condition(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.post(reverse('alerts:alert_create_condition', args=[alert.id]), {
            'indicator_id': self.indicator.id,
            'operator': '>=',
            'threshold_value': '65.5',
        })
        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        self.assertTrue(alert.conditions.filter(operator='>=', threshold_value='65.5').exists())

    def test_alert_cannot_remove_its_only_condition(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        alert.conditions.add(self.condition)
        resp = self.client.post(reverse('alerts:alert_remove_condition', args=[alert.id, self.condition.id]))
        self.assertRedirects(resp, reverse('alerts:alert_detail', args=[alert.id]))
        self.assertIn(self.condition, alert.conditions.all())

    def test_alert_detail_is_the_single_management_screen(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        response = self.client.get(reverse('alerts:alert_detail', args=[alert.id]))

        self.assertContains(response, 'Gestionar alerta')
        self.assertContains(response, 'new TomSelect(stockSelect')
        self.assertContains(response, 'Agregar condición')

        list_response = self.client.get(reverse('alerts:alert_list'))
        self.assertContains(list_response, 'Gestionar')
        self.assertNotContains(list_response, '>Ver<')
        self.assertNotContains(list_response, '>Editar<')

    def test_alert_delete(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        resp = self.client.post(reverse('alerts:alert_delete', args=[alert.id]))
        self.assertRedirects(resp, reverse('alerts:alert_list'))
        self.assertFalse(Alert.objects.filter(id=alert.id).exists())

    def test_destructive_alert_actions_reject_get(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        alert.conditions.add(self.condition)

        delete_response = self.client.get(reverse('alerts:alert_delete', args=[alert.id]))
        remove_response = self.client.get(
            reverse('alerts:alert_remove_condition', args=[alert.id, self.condition.id])
        )

        self.assertEqual(delete_response.status_code, 405)
        self.assertEqual(remove_response.status_code, 405)
        self.assertTrue(Alert.objects.filter(id=alert.id).exists())
        self.assertIn(self.condition, alert.conditions.all())

    def test_condition_create_page_and_post(self):
        get_response = self.client.get(reverse('alerts:condition_create'))
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, 'Nueva condición de alerta')

        post_response = self.client.post(reverse('alerts:condition_create'), {
            'indicator_id': self.indicator.id,
            'operator': '>=',
            'threshold_value': '65.5',
        })
        self.assertRedirects(post_response, reverse('alerts:condition_list'))
        self.assertTrue(AlertCondition.objects.filter(operator='>=', threshold_value='65.5').exists())

    def test_condition_create_rejects_invalid_input(self):
        response = self.client.post(reverse('alerts:condition_create'), {
            'indicator_id': self.indicator.id,
            'operator': 'invalido',
            'threshold_value': '-1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)

    def test_other_users_alert_returns_404(self):
        alert = Alert.objects.create(user=self.user, stock=self.stock, name='RSI Alert')
        other_user = User.objects.create_user(
            first_name='Otro', last_name='Usuario', email='otro@example.com', password='testpass123'
        )
        other_client = Client()
        other_client.force_login(other_user)
        resp = other_client.get(reverse('alerts:alert_detail', args=[alert.id]))
        self.assertEqual(resp.status_code, 404)


class AlertCommandsTest(TestCase):
    def test_seed_indicators_is_idempotent(self):
        call_command('seed_technical_indicators', stdout=StringIO())
        first_count = TechnicalIndicator.objects.count()
        call_command('seed_technical_indicators', stdout=StringIO())

        self.assertEqual(first_count, 7)
        self.assertEqual(TechnicalIndicator.objects.count(), 7)
        self.assertTrue(TechnicalIndicator.objects.filter(name='RSI', period=14).exists())
        self.assertTrue(TechnicalIndicator.objects.filter(name='SMA 50', period=50).exists())

    @patch('alerts.management.commands.evaluate_alerts.AlertManager.evaluate_active_alerts')
    def test_evaluate_alerts_command_reports_summary(self, mock_evaluate):
        mock_evaluate.return_value = {
            'evaluated': 2, 'triggered': 1, 'cooldown': 4, 'skipped': 3, 'errors': 0,
        }
        output = StringIO()

        call_command('evaluate_alerts', stdout=output)

        self.assertIn('2 evaluadas', output.getvalue())
        self.assertIn('1 disparadas', output.getvalue())
        self.assertIn('4 en cooldown', output.getvalue())
