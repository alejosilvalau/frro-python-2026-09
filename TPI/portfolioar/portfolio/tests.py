from datetime import datetime

from django.test import TestCase

from core.models import User, Sector, Broker, Stock
from portfolio.models import Position, Order
from portfolio.business import PortfolioManager


class PositionModelTest(TestCase):
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
        self.position = Position.objects.create(
            user=self.user,
            stock=self.stock,
            broker=self.broker,
            amount=10,
            stock_price_local=15000.00,
            stock_price_usd=150.00,
            purchased_at=datetime(2024, 1, 1)
        )

    def test_position_creation(self):
        self.assertEqual(self.position.user, self.user)
        self.assertEqual(self.position.stock, self.stock)
        self.assertEqual(self.position.broker, self.broker)
        self.assertEqual(self.position.amount, 10)
        self.assertEqual(self.position.stock_price_local, 15000.00)
        self.assertEqual(self.position.stock_price_usd, 150.00)

    def test_position_str(self):
        self.assertEqual(str(self.position), 'AAPL - 10 unidades')


class OrderModelTest(TestCase):
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
        self.position = Position.objects.create(
            user=self.user,
            stock=self.stock,
            broker=self.broker,
            amount=10,
            stock_price_local=15000.00,
            stock_price_usd=150.00,
            purchased_at=datetime(2024, 1, 1)
        )
        self.order = Order.objects.create(
            position=self.position,
            amount=5,
            fulfill_datetime=datetime(2024, 1, 15),
            total_fees=100.00,
            price_local=16000.00,
            price_usd=160.00
        )

    def test_order_creation(self):
        self.assertEqual(self.order.position, self.position)
        self.assertEqual(self.order.amount, 5)
        self.assertEqual(self.order.total_fees, 100.00)
        self.assertEqual(self.order.price_local, 16000.00)
        self.assertEqual(self.order.price_usd, 160.00)

    def test_order_str(self):
        self.assertEqual(str(self.order), f'Orden {self.order.id} - AAPL')


class PortfolioManagerTest(TestCase):
    def setUp(self):
        self.portfolio_manager = PortfolioManager()

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
        self.position = Position.objects.create(
            user=self.user,
            stock=self.stock,
            broker=self.broker,
            amount=10,
            stock_price_local=15000.00,
            stock_price_usd=150.00,
            purchased_at=datetime(2024, 1, 1)
        )

    def test_calculate_position_performance(self):
        performance = self.portfolio_manager.calculate_position_performance(self.position)

        self.assertIn('invested_amount', performance)
        self.assertIn('current_value', performance)
        self.assertIn('profit_loss', performance)
        self.assertIn('profit_loss_percentage', performance)
        self.assertIn('annualized_return', performance)
        self.assertIn('days_held', performance)

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

    def test_update_position_validation(self):
        with self.assertRaises(ValueError):
            self.portfolio_manager.update_position(self.position.id, -1, 15000.00, 150.00)
