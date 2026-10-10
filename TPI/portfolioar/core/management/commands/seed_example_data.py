from datetime import time
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from alerts.business import AlertManager, IndicatorManager
from alerts.models import TechnicalIndicator
from core.models import Broker, Stock
from portfolio.business import (
    CashManager,
    LotManager,
    PortfolioManager,
    SaleManager,
    last_business_day,
)
from portfolio.models import CashPosition, Lot, Position, Sale

# Moneda de negociación requerida por validate_purchase_currency.
STOCK_CURRENCIES = {'GGAL': 'ARS', 'YPF': 'ARS', 'AAPL': 'ARS', 'MSFT': 'USD'}

DEPOSITS = [
    ('ARS', 5_000_000, 'Seed ejemplo sueldo'),
    ('USD', 10_000, 'Seed ejemplo USD'),
]

WITHDRAW_DESC = 'Seed ejemplo retiro'
ALERT_NAME = 'Alerta ejemplo GGAL'


def aware_business_day(days_back):
    day = last_business_day(timezone.localdate() - timedelta(days=days_back))
    dt = timezone.datetime.combine(day, time(17, 0))
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class Command(BaseCommand):
    help = (
        'Carga datos de ejemplo usando los managers de la app (con sus validaciones). '
        'Idempotente: omite lo que ya existe.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='alejo', help='Usuario destino (debe existir).')
        parser.add_argument('--ccl', default='1400', help='CCL manual para pricing offline.')

    def handle(self, *args, **options):
        username = options['username']
        ccl = options['ccl']
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f'No existe el usuario {username!r}. Crealo antes (createsuperuser o register).') from exc

        for ticker, currency in STOCK_CURRENCIES.items():
            stock = Stock.objects.filter(ticker=ticker).first()
            if stock is None:
                self.stdout.write(f'Stock {ticker} no existe, se omite')
                continue
            if stock.trading_currency != currency:
                stock.trading_currency = currency
                stock.save(update_fields=['trading_currency'])
                self.stdout.write(self.style.SUCCESS(f'Stock {ticker} -> {currency}'))

        stats = IndicatorManager().seed_defaults()
        self.stdout.write(self.style.SUCCESS(f"Indicadores: {stats['created']} creados, {stats['existing']} existentes."))

        cash_manager = CashManager()
        for currency, amount, description in DEPOSITS:
            if CashPosition.objects.filter(user=user, currency=currency, description=description).exists():
                self.stdout.write(f'Liquidez {currency} ya existía, no se duplicó')
                continue
            cash_manager.add_cash(user.id, currency, amount, description)
            self.stdout.write(self.style.SUCCESS(f'Liquidez inicial {currency} {amount} cargada'))

        buy_at = aware_business_day(6)
        lot_at = aware_business_day(4)
        sale_at = aware_business_day(2)

        portfolio_manager = PortfolioManager()
        lot_manager = LotManager()
        sale_manager = SaleManager()
        try:
            broker = Broker.objects.get(name__icontains='InvertirOnline')
        except Broker.DoesNotExist as exc:
            raise CommandError('No hay brokers cargados. Corré seed_instruments_from_iol primero.') from exc
        ggal = Stock.objects.get(ticker='GGAL')
        msft = Stock.objects.get(ticker='MSFT')

        position = Position.objects.filter(user=user, stock=ggal).first()
        if position is None:
            position = portfolio_manager.add_position(
                user.id, ggal.id, broker.id, 10, Decimal('1500'),
                buy_at, 'ARS', price_input_currency='ARS', manual_ccl_rate=ccl,
            )
            self.stdout.write(self.style.SUCCESS(f'Posición GGAL creada: {position.id}'))
        else:
            self.stdout.write(f'Posición GGAL ya existía: {position.id}')

        if Lot.objects.filter(position=position).count() < 2:
            lot = lot_manager.add_lot(
                position.id, 5, Decimal('1600'), lot_at, 'ARS', 0,
                price_input_currency='ARS', manual_ccl_rate=ccl,
            )
            self.stdout.write(self.style.SUCCESS(f'Lote agregado: {lot.id}'))
        else:
            self.stdout.write('Lotes GGAL ya existían, no se duplicaron')

        position_usd = Position.objects.filter(user=user, stock=msft).first()
        if position_usd is None:
            position_usd = portfolio_manager.add_position(
                user.id, msft.id, broker.id, 5, Decimal('400'),
                buy_at, 'USD', price_input_currency='USD', manual_ccl_rate=ccl,
            )
            self.stdout.write(self.style.SUCCESS(f'Posición MSFT creada: {position_usd.id}'))
        else:
            self.stdout.write(f'Posición MSFT ya existía: {position_usd.id}')

        if not Sale.objects.filter(position=position).exists():
            sale = sale_manager.add_sale(
                position.id, 4, Decimal('1750'), sale_at, 'ARS',
                price_input_currency='ARS', manual_ccl_rate=ccl,
            )
            self.stdout.write(self.style.SUCCESS(f'Venta creada: {sale.id} (P&L ARS {sale.realized_pnl_ars})'))
        else:
            self.stdout.write('Venta GGAL ya existía, no se duplicó')

        if not CashPosition.objects.filter(user=user, description=WITHDRAW_DESC).exists():
            withdrawal = cash_manager.withdraw_cash(user.id, 'ARS', 50_000, WITHDRAW_DESC)
            self.stdout.write(self.style.SUCCESS(f'Retiro creado: {withdrawal.id} ({withdrawal.amount})'))
        else:
            self.stdout.write('Retiro ya existía, no se duplicó')

        alert_manager = AlertManager()
        rsi = TechnicalIndicator.objects.filter(name='RSI').first()
        if rsi is not None and not alert_manager.get_user_alerts(user.id).filter(name=ALERT_NAME).exists():
            alert = alert_manager.create_alert_with_condition(
                user.id, ggal.id, ALERT_NAME, rsi.id, '>', Decimal('70'),
            )
            self.stdout.write(self.style.SUCCESS(f'Alerta creada: {alert.id}'))
        else:
            self.stdout.write('Alerta ya existía, no se duplicó')

        totals = cash_manager.get_totals(user.id)
        self.stdout.write(self.style.SUCCESS(
            f"Listo. Disponible ARS {totals['available_ars']} / USD {totals['available_usd']}."
        ))
