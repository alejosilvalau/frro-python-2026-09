from django.test import TestCase

from core.models import User, Sector, Broker, Stock


class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            first_name='Juan',
            last_name='Pérez',
            email='juan@example.com',
            password='testpass123',
            phone='1234567890',
            birthdate='1990-01-01'
        )

    def test_user_creation(self):
        self.assertEqual(self.user.first_name, 'Juan')
        self.assertEqual(self.user.last_name, 'Pérez')
        self.assertEqual(self.user.email, 'juan@example.com')
        self.assertEqual(self.user.phone, '1234567890')

    def test_user_str(self):
        self.assertEqual(str(self.user), 'Juan Pérez')


class SectorModelTest(TestCase):
    def setUp(self):
        self.sector = Sector.objects.create(
            name='Technology',
            description='Technology sector',
            primary=True
        )

    def test_sector_creation(self):
        self.assertEqual(self.sector.name, 'Technology')
        self.assertEqual(self.sector.description, 'Technology sector')
        self.assertTrue(self.sector.primary)

    def test_sector_str(self):
        self.assertEqual(str(self.sector), 'Technology')


class BrokerModelTest(TestCase):
    def setUp(self):
        self.broker = Broker.objects.create(
            name='IOL',
            link='https://invertironline.com'
        )

    def test_broker_creation(self):
        self.assertEqual(self.broker.name, 'IOL')
        self.assertEqual(self.broker.link, 'https://invertironline.com')

    def test_broker_str(self):
        self.assertEqual(str(self.broker), 'IOL')


class StockModelTest(TestCase):
    def setUp(self):
        self.sector = Sector.objects.create(name='Technology')
        self.stock = Stock.objects.create(
            ticker='AAPL',
            company_name='Apple Inc.',
            sector=self.sector
        )

    def test_stock_creation(self):
        self.assertEqual(self.stock.ticker, 'AAPL')
        self.assertEqual(self.stock.company_name, 'Apple Inc.')
        self.assertEqual(self.stock.sector, self.sector)

    def test_stock_str(self):
        self.assertEqual(str(self.stock), 'AAPL - Apple Inc.')
