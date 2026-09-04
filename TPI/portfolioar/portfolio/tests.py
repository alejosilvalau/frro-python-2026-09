from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Sector, Broker, Stock
from portfolio.models import Position, Lot, CashPosition
from portfolio.business import PortfolioManager, LotManager, SaleManager, CashManager


class PortfolioTestBase(TestCase):
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
        self.broker = Broker.objects.create(name='IOL')
        CashPosition.objects.create(user=self.user, currency='ARS', amount=10_000_000)
        CashPosition.objects.create(user=self.user, currency='USD', amount=10_000)

        self.portfolio_manager = PortfolioManager()
        self.lot_manager = LotManager()
        self.sale_manager = SaleManager()
        self.cash_manager = CashManager()


class PositionModelTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 15000.00, 150.00, datetime(2024, 1, 1)
        )

    def test_position_creation(self):
        self.assertEqual(self.position.user, self.user)
        self.assertEqual(self.position.stock, self.stock)
        self.assertEqual(self.position.broker, self.broker)
        self.assertEqual(self.position.status, 'open')

    def test_position_str(self):
        self.assertEqual(str(self.position), 'AAPL (Abierta)')


class LotModelTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 15000.00, 150.00, datetime(2024, 1, 1)
        )
        self.lot = self.lot_manager.add_lot(
            self.position.id, 5, 16000.00, 160.00, datetime(2024, 1, 15), fees=100.00
        )

    def test_lot_creation(self):
        self.assertEqual(self.lot.position, self.position)
        self.assertEqual(self.lot.amount, 5)
        self.assertEqual(self.lot.fees, 100.00)
        self.assertEqual(self.lot.price_local, 16000.00)
        self.assertEqual(self.lot.price_usd, 160.00)

    def test_lot_str(self):
        self.assertEqual(str(self.lot), f"Lote {self.lot.id} - AAPL x5")

    def test_lot_purchase_debits_cash(self):
        available = self.cash_manager.get_available(self.user.id, 'ARS')
        # 10_000_000 - (10*15000) - (5*16000)
        self.assertEqual(available, 10_000_000 - 150000 - 80000)

    def test_add_lot_insufficient_liquidity_raises(self):
        with self.assertRaises(ValueError):
            self.lot_manager.add_lot(
                self.position.id, 1_000_000, 16000.00, 160.00, datetime(2024, 1, 16)
            )


class PortfolioManagerTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 15000.00, 150.00, datetime(2024, 1, 1)
        )

    def test_calculate_position_performance(self):
        performance = self.portfolio_manager.calculate_position_performance(self.position)

        self.assertIn('open_amount', performance)
        self.assertIn('invested_amount', performance)
        self.assertIn('current_value', performance)
        self.assertIn('profit_loss', performance)
        self.assertIn('profit_loss_percentage', performance)
        self.assertIn('annualized_return', performance)
        self.assertIn('days_held', performance)
        self.assertIn('realized_pnl_ars', performance)
        self.assertIn('realized_pnl_usd', performance)
        self.assertEqual(performance['open_amount'], 10)

    def test_compare_with_sp500(self):
        comparison = self.portfolio_manager.compare_with_sp500(self.position)

        self.assertIn('sp500_return', comparison)
        self.assertIn('alpha', comparison)

    def test_compare_with_inflation(self):
        comparison = self.portfolio_manager.compare_with_inflation(self.position)

        self.assertIn('inflation', comparison)
        self.assertIn('real_return', comparison)

    def test_calculate_portfolio_summary(self):
        summary = self.portfolio_manager.calculate_portfolio_summary(self.user.id)

        self.assertIn('total_invested', summary)
        self.assertIn('total_current_value', summary)
        self.assertIn('profit_loss', summary)
        self.assertIn('profit_loss_percentage', summary)
        self.assertIn('position_count', summary)
        self.assertIn('sp500_return', summary)
        self.assertIn('alpha', summary)
        self.assertIn('inflation', summary)
        self.assertIn('real_return', summary)
        self.assertIn('sector_distribution', summary)
        self.assertIn('total_realized_pnl_ars', summary)

    def test_get_technical_indicators(self):
        indicators = self.portfolio_manager.get_technical_indicators(self.position)

        self.assertIn('rsi', indicators)
        self.assertIn('macd', indicators)
        self.assertIn('macd_signal', indicators)
        self.assertIn('macd_histogram', indicators)
        self.assertIn('sma_20', indicators)
        self.assertIn('sma_50', indicators)
        self.assertIn('ema_30', indicators)
        self.assertIn('volume_relative', indicators)
        self.assertIn('volatility', indicators)

    def test_add_position_validation(self):
        with self.assertRaises(ValueError):
            self.portfolio_manager.add_position(
                self.user.id, self.stock.id, self.broker.id, 0, 15000.00, 150.00, '2024-01-01'
            )

    def test_remove_position_without_sales_refunds_cash(self):
        available_before = self.cash_manager.get_available(self.user.id, 'ARS')
        self.portfolio_manager.remove_position(self.position.id)
        available_after = self.cash_manager.get_available(self.user.id, 'ARS')
        self.assertEqual(available_after, available_before + 150000)
        self.assertFalse(Position.objects.filter(id=self.position.id).exists())

    def test_remove_position_with_sales_raises(self):
        self.sale_manager.add_sale(self.position.id, 4, 17000.00, 170.00, datetime(2024, 2, 1))
        with self.assertRaises(ValueError):
            self.portfolio_manager.remove_position(self.position.id)


class SaleFIFOTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 15000.00, 150.00, datetime(2024, 1, 1)
        )
        self.lot2 = self.lot_manager.add_lot(
            self.position.id, 10, 20000.00, 200.00, datetime(2024, 2, 1)
        )

    def test_partial_sell_reduces_open_amount(self):
        self.sale_manager.add_sale(self.position.id, 5, 25000.00, 250.00, datetime(2024, 3, 1))
        summary = self.portfolio_manager.get_open_position_summary(self.position)
        self.assertEqual(summary['open_amount'], 15)

    def test_fifo_consumes_oldest_lot_first(self):
        # 10 @ 15000 (oldest) + 10 @ 20000 (newest); selling 12 should consume
        # all 10 of the oldest lot and 2 of the newest.
        sale = self.sale_manager.add_sale(self.position.id, 12, 25000.00, 250.00, datetime(2024, 3, 1))
        consumed = list(sale.consumed_lots.all().order_by('lot__purchased_at'))
        self.assertEqual(len(consumed), 2)
        self.assertEqual(consumed[0].amount_consumed, 10)
        self.assertEqual(consumed[0].cost_price_local, 15000.00)
        self.assertEqual(consumed[1].amount_consumed, 2)
        self.assertEqual(consumed[1].cost_price_local, 20000.00)

    def test_realized_pnl_correct(self):
        # Sell 10 shares (the whole oldest lot bought at 15000) at 25000 -> pnl = 10*(25000-15000)
        sale = self.sale_manager.add_sale(self.position.id, 10, 25000.00, 250.00, datetime(2024, 3, 1))
        self.assertEqual(sale.realized_pnl_ars, 100000)

    def test_sell_more_than_available_raises(self):
        with self.assertRaises(ValueError):
            self.sale_manager.add_sale(self.position.id, 100, 25000.00, 250.00, datetime(2024, 3, 1))

    def test_sell_credits_cash(self):
        available_before = self.cash_manager.get_available(self.user.id, 'ARS')
        self.sale_manager.add_sale(self.position.id, 5, 25000.00, 250.00, datetime(2024, 3, 1))
        available_after = self.cash_manager.get_available(self.user.id, 'ARS')
        self.assertEqual(available_after, available_before + 125000)

    def test_selling_all_open_lots_closes_position(self):
        self.sale_manager.add_sale(self.position.id, 20, 25000.00, 250.00, datetime(2024, 3, 1))
        self.position.refresh_from_db()
        self.assertEqual(self.position.status, 'closed')


class PositionCreateViewTest(PortfolioTestBase):
    """CU01 - Registrar posición de compra."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.valid_data = {
            'stock_id': self.stock.id,
            'broker_id': self.broker.id,
            'amount': '10',
            'price_local': '1000',
            'price_usd': '10',
            'purchased_at': '2024-01-01T10:00',
            'purchase_currency': 'ARS',
        }

    def test_get_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('portfolio:position_create'))
        self.assertEqual(resp.status_code, 302)

    def test_get_renders_form_with_available_balances(self):
        resp = self.client.get(reverse('portfolio:position_create'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('available_ars', resp.context)
        self.assertIn('available_usd', resp.context)

    def test_post_valid_creates_position_and_debits_cash(self):
        resp = self.client.post(reverse('portfolio:position_create'), self.valid_data)
        self.assertRedirects(resp, reverse('portfolio:position_list'))
        self.assertEqual(Position.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.cash_manager.get_available(self.user.id, 'ARS'), Decimal('10000000') - 10000)

    def test_post_invalid_amount_shows_error_and_does_not_create(self):
        data = {**self.valid_data, 'amount': '0'}
        resp = self.client.post(reverse('portfolio:position_create'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
        self.assertEqual(Position.objects.filter(user=self.user).count(), 0)

    def test_post_insufficient_liquidity_shows_error_and_does_not_create(self):
        data = {**self.valid_data, 'amount': '1000000'}
        resp = self.client.post(reverse('portfolio:position_create'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Liquidez insuficiente', resp.context['error'])
        self.assertEqual(Position.objects.filter(user=self.user).count(), 0)


class PositionDetailViewTest(PortfolioTestBase):
    """CU02 - Consultar rendimiento de una posición."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 1000.0, 10.0, datetime(2024, 1, 1)
        )

    def test_get_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('portfolio:position_detail', args=[self.position.id]))
        self.assertEqual(resp.status_code, 302)

    def test_other_users_position_returns_404(self):
        other_user = User.objects.create_user(
            first_name='Otro', last_name='Usuario', email='otro@example.com', password='testpass123'
        )
        other_client = Client()
        other_client.force_login(other_user)
        resp = other_client.get(reverse('portfolio:position_detail', args=[self.position.id]))
        self.assertEqual(resp.status_code, 404)

    @patch('portfolio.business.get_historical_prices', return_value=None)
    @patch('portfolio.business.ExternalAPIs.get_indec_inflation', return_value=Decimal('5'))
    @patch('portfolio.business.ExternalAPIs.get_sp500_performance', return_value=Decimal('8'))
    @patch('portfolio.business.ExternalAPIs.get_current_price', return_value=Decimal('1200'))
    def test_shows_unrealized_performance_sp500_and_inflation(self, mock_price, mock_sp500, mock_indec, mock_hist):
        resp = self.client.get(reverse('portfolio:position_detail', args=[self.position.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['performance']['open_amount'], 10)
        self.assertEqual(resp.context['performance']['profit_loss'], Decimal('2000'))
        self.assertEqual(resp.context['sp500']['sp500_return'], Decimal('8'))
        self.assertEqual(resp.context['inflation']['inflation'], Decimal('5'))

    @patch('portfolio.business.get_historical_prices', return_value=None)
    @patch('portfolio.business.ExternalAPIs.get_sp500_performance', return_value=Decimal('0'))
    @patch('portfolio.business.ExternalAPIs.get_current_price', return_value=Decimal('1200'))
    def test_indec_failure_is_handled_gracefully(self, mock_price, mock_sp500, mock_hist):
        with patch('portfolio.business.requests.get', side_effect=Exception('INDEC no responde')):
            resp = self.client.get(reverse('portfolio:position_detail', args=[self.position.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['inflation']['inflation'], Decimal('0'))


class LotViewsTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 1000.0, 10.0, datetime(2024, 1, 1)
        )

    def test_get_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('portfolio:lot_create', args=[self.position.id]))
        self.assertEqual(resp.status_code, 302)

    def test_get_shows_available_balances(self):
        resp = self.client.get(reverse('portfolio:lot_create', args=[self.position.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('available_ars', resp.context)

    def test_post_valid_adds_lot_and_debits_cash(self):
        data = {
            'amount': '5', 'price_local': '1200', 'price_usd': '12',
            'purchased_at': '2024-02-01T10:00', 'purchase_currency': 'ARS', 'fees': '0',
        }
        resp = self.client.post(reverse('portfolio:lot_create', args=[self.position.id]), data)
        self.assertRedirects(resp, reverse('portfolio:position_detail', args=[self.position.id]))
        summary = self.portfolio_manager.get_open_position_summary(self.position)
        self.assertEqual(summary['open_amount'], 15)

    def test_post_insufficient_liquidity_shows_error(self):
        data = {
            'amount': '1000000', 'price_local': '1200', 'price_usd': '12',
            'purchased_at': '2024-02-01T10:00', 'purchase_currency': 'ARS', 'fees': '0',
        }
        resp = self.client.post(reverse('portfolio:lot_create', args=[self.position.id]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)

    def test_delete_untouched_lot_refunds_cash(self):
        lot = self.lot_manager.add_lot(self.position.id, 5, 1200.0, 12.0, datetime(2024, 2, 1))
        available_before = self.cash_manager.get_available(self.user.id, 'ARS')
        resp = self.client.get(reverse('portfolio:lot_delete', args=[lot.id]))
        self.assertRedirects(resp, reverse('portfolio:position_detail', args=[self.position.id]))
        available_after = self.cash_manager.get_available(self.user.id, 'ARS')
        self.assertEqual(available_after, available_before + 6000)

    def test_delete_sold_lot_is_blocked_with_message(self):
        self.sale_manager.add_sale(self.position.id, 10, 1500.0, 15.0, datetime(2024, 3, 1))
        lot = list(self.lot_manager.get_position_lots(self.position.id))[0]
        resp = self.client.get(reverse('portfolio:lot_delete', args=[lot.id]), follow=True)
        stored_messages = list(resp.context['messages'])
        self.assertTrue(any('vendido' in str(m) for m in stored_messages))
        self.assertTrue(Lot.objects.filter(id=lot.id).exists())


class SaleViewTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 1000.0, 10.0, datetime(2024, 1, 1)
        )

    def test_get_shows_open_summary(self):
        resp = self.client.get(reverse('portfolio:sale_create', args=[self.position.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['open_summary']['open_amount'], 10)

    def test_post_valid_reduces_open_amount_and_credits_cash(self):
        available_before = self.cash_manager.get_available(self.user.id, 'ARS')
        data = {
            'amount': '4', 'price_local': '1500', 'price_usd': '15',
            'sold_at': '2024-03-01T10:00', 'sell_currency': 'ARS',
        }
        resp = self.client.post(reverse('portfolio:sale_create', args=[self.position.id]), data)
        self.assertRedirects(resp, reverse('portfolio:position_detail', args=[self.position.id]))
        summary = self.portfolio_manager.get_open_position_summary(self.position)
        self.assertEqual(summary['open_amount'], 6)
        available_after = self.cash_manager.get_available(self.user.id, 'ARS')
        self.assertEqual(available_after, available_before + 6000)

    def test_post_more_than_open_shows_error(self):
        data = {
            'amount': '100', 'price_local': '1500', 'price_usd': '15',
            'sold_at': '2024-03-01T10:00', 'sell_currency': 'ARS',
        }
        resp = self.client.post(reverse('portfolio:sale_create', args=[self.position.id]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)


class PositionDeleteViewTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 1000.0, 10.0, datetime(2024, 1, 1)
        )

    def test_delete_without_sales_refunds_cash_and_removes_position(self):
        available_before = self.cash_manager.get_available(self.user.id, 'ARS')
        resp = self.client.get(reverse('portfolio:position_delete', args=[self.position.id]))
        self.assertRedirects(resp, reverse('portfolio:position_list'))
        self.assertFalse(Position.objects.filter(id=self.position.id).exists())
        available_after = self.cash_manager.get_available(self.user.id, 'ARS')
        self.assertEqual(available_after, available_before + 10000)

    def test_delete_with_sales_is_blocked_with_message(self):
        self.sale_manager.add_sale(self.position.id, 5, 1500.0, 15.0, datetime(2024, 3, 1))
        resp = self.client.get(reverse('portfolio:position_delete', args=[self.position.id]), follow=True)
        stored_messages = list(resp.context['messages'])
        self.assertTrue(any('ventas' in str(m) for m in stored_messages))
        self.assertTrue(Position.objects.filter(id=self.position.id).exists())


class CashViewsTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_cash_list_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('portfolio:cash_list'))
        self.assertEqual(resp.status_code, 302)

    def test_cash_list_renders(self):
        resp = self.client.get(reverse('portfolio:cash_list'))
        self.assertEqual(resp.status_code, 200)

    def test_cash_create_post_valid(self):
        resp = self.client.post(reverse('portfolio:cash_create'), {
            'currency': 'ARS', 'amount': '50000', 'description': 'Sueldo',
        })
        self.assertRedirects(resp, reverse('portfolio:cash_list'))
        self.assertTrue(CashPosition.objects.filter(user=self.user, description='Sueldo').exists())

    def test_cash_create_post_invalid_amount_shows_error(self):
        resp = self.client.post(reverse('portfolio:cash_create'), {'currency': 'ARS', 'amount': '0'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)

    def test_cash_update_post_valid(self):
        cash = self.cash_manager.add_cash(self.user.id, 'ARS', 1000, 'Original')
        resp = self.client.post(reverse('portfolio:cash_update', args=[cash.id]), {
            'amount': '2000', 'description': 'Actualizado',
        })
        self.assertRedirects(resp, reverse('portfolio:cash_list'))
        cash.refresh_from_db()
        self.assertEqual(cash.amount, 2000)

    def test_cash_delete(self):
        cash = self.cash_manager.add_cash(self.user.id, 'ARS', 1000, 'Para borrar')
        resp = self.client.get(reverse('portfolio:cash_delete', args=[cash.id]))
        self.assertRedirects(resp, reverse('portfolio:cash_list'))
        self.assertFalse(CashPosition.objects.filter(id=cash.id).exists())

    def test_other_users_cash_returns_404(self):
        cash = self.cash_manager.add_cash(self.user.id, 'ARS', 1000, 'Privado')
        other_user = User.objects.create_user(
            first_name='Otro', last_name='Usuario', email='otro2@example.com', password='testpass123'
        )
        other_client = Client()
        other_client.force_login(other_user)
        resp = other_client.get(reverse('portfolio:cash_update', args=[cash.id]))
        self.assertEqual(resp.status_code, 404)


class DashboardAndListViewsTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.position = self.portfolio_manager.add_position(
            self.user.id, self.stock.id, self.broker.id, 10, 1000.0, 10.0, datetime(2024, 1, 1)
        )

    def test_dashboard_requires_login(self):
        anon_client = Client()
        resp = anon_client.get(reverse('portfolio:dashboard'))
        self.assertEqual(resp.status_code, 302)

    @patch('portfolio.business.get_historical_prices', return_value=None)
    @patch('portfolio.business.ExternalAPIs.get_indec_inflation', return_value=Decimal('0'))
    @patch('portfolio.business.ExternalAPIs.get_sp500_performance', return_value=Decimal('0'))
    @patch('portfolio.business.ExternalAPIs.get_current_price', return_value=Decimal('1100'))
    def test_dashboard_renders(self, *mocks):
        resp = self.client.get(reverse('portfolio:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_position_list_renders_with_pagination_context(self):
        resp = self.client.get(reverse('portfolio:position_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('page', resp.context)


class ApiInstrumentPriceViewTest(PortfolioTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_requires_stock_id(self):
        resp = self.client.get(reverse('portfolio:api_instrument_price'))
        self.assertEqual(resp.status_code, 400)

    @patch('portfolio.views.get_ccl_rate', return_value=1000.0)
    @patch('portfolio.views.get_stock_price_from_iol', return_value=5000.0)
    def test_success_returns_prices(self, mock_iol, mock_ccl):
        resp = self.client.get(reverse('portfolio:api_instrument_price'), {'stock_id': self.stock.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['price_ars'], 5000.0)
        self.assertEqual(data['price_usd'], 5.0)

    @patch('portfolio.views.get_stock_price_from_iol', side_effect=Exception('IOL down'))
    def test_iol_failure_returns_502(self, mock_iol):
        resp = self.client.get(reverse('portfolio:api_instrument_price'), {'stock_id': self.stock.id})
        self.assertEqual(resp.status_code, 502)
