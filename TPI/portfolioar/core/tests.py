import csv
from io import StringIO
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Sector, Broker, Stock
from core.business import AuthManager, StockManager


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

    def test_quote_unit_remains_one_for_equities_and_one_hundred_for_fixed_income(self):
        manager = StockManager()
        self.assertEqual(manager.get_quote_unit(self.stock), 1)
        for tipo in ('bono', 'letra'):
            fixed_income = Stock.objects.create(
                ticker=f'{tipo.upper()}-TEST', company_name='Test instrument', tipo=tipo
            )
            self.assertEqual(manager.get_quote_unit(fixed_income), 100)


class InstrumentClassificationCommandTest(TestCase):
    def setUp(self):
        self.sector = Sector.objects.create(name='Manual')
        self.base = Stock.objects.create(ticker='AAPL', company_name='Cedear Apple Inc.', tipo='cedear')
        self.ccl = Stock.objects.create(ticker='AAPLC', company_name='Cedear Apple Inc. clase CCL', tipo='cedear')
        self.official = Stock.objects.create(ticker='AAPLD', company_name='Cedear Apple Inc. Esc.', tipo='cedear')
        self.unrelated = Stock.objects.create(ticker='AAPLX', company_name='Cedear Apple Inc.', tipo='cedear')

    def _catalog(self, rows):
        handle = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', suffix='.csv', delete=False)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        writer = csv.DictWriter(handle, fieldnames=[
            'ticker', 'tipo', 'sector', 'cedear_kind', 'issuer_type', 'rate_reference',
            'payment_style', 'instrument_family', 'underlying_ticker', 'source', 'source_date',
        ])
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        return handle.name

    def _row(self):
        return {
            'ticker': 'AAPL', 'tipo': 'cedear', 'sector': 'Tecnología de la Información',
            'cedear_kind': 'company', 'issuer_type': '', 'rate_reference': '',
            'payment_style': '', 'instrument_family': '', 'underlying_ticker': '',
            'source': 'IAMC, 24/09/2026', 'source_date': '2026-09-24',
        }

    def test_dry_run_does_not_write_and_apply_links_explicit_c_and_d_variants(self):
        catalog = self._catalog([self._row()])
        output = StringIO()
        call_command('sync_instrument_classification', catalog=catalog, stdout=output)
        self.assertIn('Simulación (sin escrituras)', output.getvalue())
        self.assertIsNone(Stock.objects.get(pk=self.base.pk).cedear_kind)
        self.assertFalse(Sector.objects.filter(name='Tecnología de la Información').exists())

        call_command('sync_instrument_classification', catalog=catalog, apply=True, stdout=Mock())
        for ticker in ('AAPL', 'AAPLC', 'AAPLD'):
            stock = Stock.objects.get(ticker=ticker)
            self.assertEqual(stock.cedear_kind, 'company')
            self.assertEqual(stock.underlying_ticker, 'AAPL')
            self.assertEqual(stock.sector.name, 'Tecnología')
        self.assertIsNone(Stock.objects.get(ticker='AAPLX').cedear_kind)

    def test_manual_classification_is_not_overwritten(self):
        self.ccl.sector = self.sector
        self.ccl.cedear_kind = 'etf'
        self.ccl.classification_manual = True
        self.ccl.save()
        call_command(
            'sync_instrument_classification', catalog=self._catalog([self._row()]),
            apply=True, stdout=Mock(),
        )
        self.ccl.refresh_from_db()
        self.assertEqual(self.ccl.sector, self.sector)
        self.assertEqual(self.ccl.cedear_kind, 'etf')

    def test_fixed_income_rules_require_explicit_family_or_issuer_evidence(self):
        cases = [
            ('AL30', 'bono', 'Bono Rep. Argentina USD Step Up 2030'),
            ('BA37D', 'bono', 'Bono Pcia. Bs. As. REGS New 2037'),
            ('S30S6', 'letra', 'LECAP S30S6'),
            ('D30S6', 'letra', 'Letra Dólar Linked D30S6'),
            ('T30A7', 'bono', 'Bono Tesoro NAC CAP V.30/04/27'),
            ('UNKNOWN', 'bono', 'Bono serie sin emisor ni tasa identificable'),
        ]
        created = [Stock.objects.create(ticker=ticker, company_name=name, tipo=kind)
                   for ticker, kind, name in cases]
        catalog = self._catalog([])

        call_command('sync_instrument_classification', catalog=catalog, apply=True, stdout=StringIO())

        indexed = {stock.ticker: Stock.objects.get(pk=stock.pk) for stock in created}
        self.assertEqual(indexed['AL30'].issuer_type, 'national')
        self.assertEqual(indexed['AL30'].payment_style, 'step_up')
        self.assertEqual(indexed['BA37D'].issuer_type, 'provincial')
        self.assertEqual(indexed['S30S6'].issuer_type, 'national')
        self.assertEqual(indexed['S30S6'].rate_reference, 'fixed')
        self.assertEqual(indexed['S30S6'].payment_style, 'capitalizable')
        self.assertEqual(indexed['D30S6'].rate_reference, 'dollar_linked')
        self.assertEqual(indexed['T30A7'].payment_style, 'capitalizable')
        self.assertIsNone(indexed['UNKNOWN'].issuer_type)
        self.assertIsNone(indexed['UNKNOWN'].rate_reference)

    def test_iamc_base_ticker_is_not_misread_as_another_tickers_d_variant(self):
        Stock.objects.create(ticker='BB', company_name='Cedear Blackberry', tipo='cedear')
        Stock.objects.create(ticker='BBD', company_name='Cedear Banco Bradesco', tipo='cedear')
        rows = [
            {**self._row(), 'ticker': 'BB', 'sector': 'Tecnología de la Información'},
            {**self._row(), 'ticker': 'BBD', 'sector': 'Servicios Financieros'},
        ]

        call_command(
            'sync_instrument_classification', catalog=self._catalog(rows), apply=True, stdout=StringIO(),
        )

        bradesco = Stock.objects.get(ticker='BBD')
        self.assertEqual(bradesco.sector.name, 'Finanzas')
        self.assertEqual(bradesco.underlying_ticker, 'BBD')


class SeedInstrumentsFromIolCommandTest(TestCase):
    def test_iol_currency_normalization_does_not_infer_from_ticker(self):
        from core.currency import normalize_iol_currency

        self.assertEqual(normalize_iol_currency('AR$'), 'ARS')
        self.assertEqual(normalize_iol_currency('US$'), 'USD')
        self.assertIsNone(normalize_iol_currency(None))

    @patch('core.management.commands.seed_instruments_from_iol._get_iol_token', return_value='fake-token')
    @patch('core.management.commands.seed_instruments_from_iol.requests.get')
    def test_imports_letras_and_updates_existing_catalog_type(self, get, _token):
        payloads = [
            {'titulos': [{'simbolo': 'EXIST', 'descripcion': 'Existing equity', 'moneda': 'AR$'}]},
            {'titulos': [{'simbolo': 'LEADER', 'descripcion': 'Leader equity', 'moneda': 'AR$'}]},
            {'titulos': [
                {'simbolo': 'AAPLC', 'descripcion': 'Cedear Apple C', 'moneda': 'US$'},
                {'simbolo': 'BBD', 'descripcion': 'Cedear Bradesco', 'moneda': 'AR$'},
            ]},
            {'titulos': [{'simbolo': 'EXIST', 'descripcion': 'Existing bond', 'moneda': 'AR$'}]},
            {'titulos': []},
            {'titulos': [{'simbolo': 'S30S6', 'descripcion': 'LECAP S30S6', 'moneda': 'AR$'}]},
        ]
        get.side_effect = [
            SimpleNamespace(json=lambda payload=payload: payload, raise_for_status=lambda: None)
            for payload in payloads
        ]
        Stock.objects.create(ticker='EXIST', company_name='Existing equity', tipo='accion')

        call_command('seed_instruments_from_iol', stdout=StringIO())

        self.assertEqual(Stock.objects.get(ticker='EXIST').tipo, 'bono')
        self.assertEqual(Stock.objects.get(ticker='LEADER').tipo, 'accion')
        self.assertEqual(Stock.objects.get(ticker='LEADER').trading_currency, 'ARS')
        self.assertEqual(Stock.objects.get(ticker='AAPLC').trading_currency, 'USD')
        self.assertEqual(Stock.objects.get(ticker='BBD').trading_currency, 'ARS')
        letter = Stock.objects.get(ticker='S30S6')
        self.assertEqual(letter.tipo, 'letra')
        self.assertEqual(letter.issuer_type, 'national')
        self.assertEqual(letter.instrument_family, 'LECAP')
        self.assertEqual(get.call_count, 6)

    @patch('core.management.commands.seed_instruments_from_iol._get_iol_token', return_value='fake-token')
    @patch('core.management.commands.seed_instruments_from_iol.requests.get')
    def test_external_failure_does_not_leave_a_partial_instrument_catalog(self, get, _token):
        from requests.exceptions import HTTPError

        good = SimpleNamespace(
            json=lambda: {'titulos': [{'simbolo': 'PARTIAL', 'descripcion': 'Partial', 'moneda': 'AR$'}]},
            raise_for_status=lambda: None,
        )
        failed = SimpleNamespace(json=lambda: {}, raise_for_status=lambda: (_ for _ in ()).throw(HTTPError()))
        get.side_effect = [good, good, good, good, failed]

        with self.assertRaises(HTTPError):
            call_command('seed_instruments_from_iol', stdout=StringIO())

        self.assertFalse(Stock.objects.exists())


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
        self.assertContains(resp, 'class="app-shell"')
        self.assertContains(resp, 'class="app-main auth-main"')
        self.assertContains(resp, 'class="content-area"')

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

    def test_register_success_shows_one_toast_on_login(self):
        response = self.client.post(reverse('core:register'), {
            'first_name': 'Ana',
            'last_name': 'Gómez',
            'email': 'ana@example.com',
            'password': 'password123',
            'password_confirm': 'password123',
        }, follow=True)

        self.assertContains(response, 'Tu cuenta fue creada. Ya podés iniciar sesión.')
        self.assertContains(response, 'class="toast text-bg-success border-0"')

        next_response = self.client.get(reverse('core:login'))
        self.assertNotContains(next_response, 'Tu cuenta fue creada. Ya podés iniciar sesión.')

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

    def test_login_post_with_csrf_token_succeeds(self):
        csrf_client = Client(enforce_csrf_checks=True)
        login_url = reverse('core:login')
        csrf_client.get(login_url)

        response = csrf_client.post(
            login_url,
            {'email': 'juan@example.com', 'password': 'testpass123'},
            HTTP_X_CSRFTOKEN=csrf_client.cookies['csrftoken'].value,
        )

        self.assertRedirects(response, reverse('portfolio:dashboard'))

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
