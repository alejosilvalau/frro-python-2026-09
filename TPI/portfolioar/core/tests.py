from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Sector, Broker, Stock
from core.business import AuthManager


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


class AuthManagerTest(TestCase):
    def setUp(self):
        self.auth_manager = AuthManager()
        self.existing_user = User.objects.create_user(
            first_name='Juan', last_name='Pérez', email='juan@example.com', password='testpass123'
        )

    def test_register_success(self):
        user = self.auth_manager.register('Ana', 'Gómez', 'ana@example.com', 'password123')
        self.assertEqual(user.email, 'ana@example.com')
        self.assertTrue(user.check_password('password123'))

    def test_register_duplicate_email_raises(self):
        """RN02: no pueden existir dos usuarios con el mismo email."""
        with self.assertRaises(ValueError):
            self.auth_manager.register('Otro', 'Usuario', 'juan@example.com', 'password123')

    def test_register_short_password_raises(self):
        """RN01: la contraseña debe tener al menos 8 caracteres."""
        with self.assertRaises(ValueError):
            self.auth_manager.register('Ana', 'Gómez', 'ana@example.com', 'short1')

    def test_login_success(self):
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get('/')
        SessionMiddleware(lambda r: None).process_request(request)

        user = self.auth_manager.login(request, 'juan@example.com', 'testpass123')
        self.assertEqual(user, self.existing_user)

    def test_login_invalid_credentials_raises(self):
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get('/')
        SessionMiddleware(lambda r: None).process_request(request)

        with self.assertRaises(ValueError):
            self.auth_manager.login(request, 'juan@example.com', 'wrongpassword')

    def test_change_password_wrong_old_password_raises(self):
        with self.assertRaises(ValueError):
            self.auth_manager.change_password(self.existing_user, 'wrongpassword', 'newpassword123')

    def test_change_password_short_new_password_raises(self):
        """RN01 también aplica al cambio de contraseña."""
        with self.assertRaises(ValueError):
            self.auth_manager.change_password(self.existing_user, 'testpass123', 'short')

    def test_change_password_success(self):
        self.auth_manager.change_password(self.existing_user, 'testpass123', 'newpassword123')
        self.existing_user.refresh_from_db()
        self.assertTrue(self.existing_user.check_password('newpassword123'))


class AuthViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            first_name='Juan', last_name='Pérez', email='juan@example.com', password='testpass123'
        )

    def test_home_shows_landing_when_anonymous(self):
        resp = self.client.get(reverse('core:home'))
        self.assertEqual(resp.status_code, 200)

    def test_home_redirects_to_dashboard_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('core:home'))
        self.assertRedirects(resp, reverse('portfolio:dashboard'))

    def test_register_success_redirects_to_login(self):
        resp = self.client.post(reverse('core:register'), {
            'first_name': 'Ana',
            'last_name': 'Gómez',
            'email': 'ana@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
            'phone': '',
            'birthdate': '',
        })
        self.assertRedirects(resp, reverse('core:login'))
        self.assertTrue(User.objects.filter(email='ana@example.com').exists())

    def test_register_password_mismatch_shows_error(self):
        resp = self.client.post(reverse('core:register'), {
            'first_name': 'Ana',
            'last_name': 'Gómez',
            'email': 'ana@example.com',
            'password': 'password123',
            'password_confirm': 'different',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
        self.assertFalse(User.objects.filter(email='ana@example.com').exists())

    def test_register_short_password_shows_error(self):
        resp = self.client.post(reverse('core:register'), {
            'first_name': 'Ana',
            'last_name': 'Gómez',
            'email': 'ana@example.com',
            'password': 'short1',
            'password_confirm': 'short1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
        self.assertFalse(User.objects.filter(email='ana@example.com').exists())

    def test_register_duplicate_email_shows_error(self):
        resp = self.client.post(reverse('core:register'), {
            'first_name': 'Otro',
            'last_name': 'Usuario',
            'email': 'juan@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)

    def test_login_success_redirects_to_dashboard(self):
        resp = self.client.post(reverse('core:login'), {
            'email': 'juan@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(resp, reverse('portfolio:dashboard'))

    def test_login_invalid_credentials_shows_error(self):
        resp = self.client.post(reverse('core:login'), {
            'email': 'juan@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)

    def test_logout_requires_login(self):
        resp = self.client.get(reverse('core:logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('core:login'), resp.url)

    def test_logout_success(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('core:logout'))
        self.assertRedirects(resp, reverse('core:home'))

    def test_profile_requires_login(self):
        resp = self.client.get(reverse('core:profile'))
        self.assertEqual(resp.status_code, 302)

    def test_profile_renders_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('core:profile'))
        self.assertEqual(resp.status_code, 200)

    def test_change_password_success(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('core:change_password'), {
            'old_password': 'testpass123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertRedirects(resp, reverse('core:profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword123'))

    def test_change_password_mismatch_shows_error(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('core:change_password'), {
            'old_password': 'testpass123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'different',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)

    def test_change_password_wrong_old_password_shows_error(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('core:change_password'), {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('error', resp.context)
