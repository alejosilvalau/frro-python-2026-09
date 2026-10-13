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
    is_business_day,
    last_business_day,
)
from portfolio.models import CashPosition, Lot, Position, Sale

# Moneda de negociación requerida por validate_purchase_currency (según IOL).
# Ojo: el ticker BYMA/IOL de YPF es YPFD (YPF.BA no existe en Yahoo).
STOCK_CURRENCIES = {'GGAL': 'ARS', 'YPFD': 'ARS', 'AAPL': 'ARS', 'MSFT': 'ARS'}
CANONICAL_TICKERS = {'YPF': 'YPFD'}

DEPOSITS = [
    ('ARS', 5_000_000, 'Seed ejemplo sueldo'),
    ('USD', 10_000, 'Seed ejemplo USD'),
]

WITHDRAW_DESC = 'Seed ejemplo retiro'
ALERT_NAME = 'Alerta ejemplo GGAL'

# Movimientos masivos: 20 compras + 20 ventas round-robin (compra 2 / venta 1).
BULK_TICKERS = ['GGAL', 'NVDA', 'YPFD']
BULK_PAIRS = 20
BULK_BUY_AMOUNT = 2
BULK_SELL_AMOUNT = 1
BULK_BASE_PRICE = Decimal('1500')
BULK_PRICE_STEP = Decimal('25')
BULK_SELL_SPREAD = Decimal('100')


def recent_business_days(count):
    """Últimos `count` días hábiles en orden cronológico (excluye hoy)."""
    days = []
    cursor = timezone.localdate() - timedelta(days=1)
    while len(days) < count and (timezone.localdate() - cursor).days < 120:
        if is_business_day(cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
    if len(days) < count:
        raise CommandError('No se pudieron reunir suficientes días hábiles para el seed masivo.')
    return list(reversed(days))


def aware_at(day):
    dt = timezone.datetime.combine(day, time(17, 0))
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


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
                buy_at, 'ARS', price_input_currency='ARS', manual_ccl_rate=ccl,
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

        # 20 compras + 20 ventas: pares (compra día N, venta día N+1) round-robin.
        # Cada venta (1) es menor que su compra (2) y posterior a ella: FIFO cubierto.
        schedule = recent_business_days(BULK_PAIRS * 2)
        bulk_positions = {}
        for ticker in BULK_TICKERS:
            stock = Stock.objects.get(ticker=ticker)
            bulk_positions[ticker] = Position.objects.filter(user=user, stock=stock).first()
        # Sana DBs seedadas con el ticker viejo: re-apunta la posición a YPFD.
        for stale, canonical in CANONICAL_TICKERS.items():
            stale_stock = Stock.objects.filter(ticker=stale).first()
            canonical_stock = Stock.objects.filter(ticker=canonical).first()
            if stale_stock is None or canonical_stock is None:
                continue
            stale_pos = Position.objects.filter(user=user, stock=stale_stock)
            if stale_pos.exists() and not Position.objects.filter(user=user, stock=canonical_stock).exists():
                stale_pos.update(stock=canonical_stock)
                self.stdout.write(self.style.SUCCESS(f'Posición {stale} migrada a {canonical}'))
            if not Position.objects.filter(stock=stale_stock).exists():
                stale_stock.delete()
                self.stdout.write(self.style.SUCCESS(f'Stock stale {stale} eliminado'))
        bulk_positions['YPFD'] = Position.objects.filter(
            user=user, stock=Stock.objects.get(ticker='YPFD')).first()

        # YPFD puede no tener posición: su primera compra del cronograma la abre
        # vía add_position (cuenta como una de las 20 compras).
        ypfd_first_pair = next(i for i in range(BULK_PAIRS) if BULK_TICKERS[i % len(BULK_TICKERS)] == 'YPFD')
        ypfd_buy_day = schedule[ypfd_first_pair * 2]
        ypfd_buy_price = BULK_BASE_PRICE + ypfd_first_pair * BULK_PRICE_STEP
        if bulk_positions['YPFD'] is None:
            ypfd = Stock.objects.get(ticker='YPFD')
            bulk_positions['YPFD'] = portfolio_manager.add_position(
                user.id, ypfd.id, broker.id, BULK_BUY_AMOUNT, ypfd_buy_price,
                aware_at(ypfd_buy_day), 'ARS', price_input_currency='ARS', manual_ccl_rate=ccl,
            )
            self.stdout.write(self.style.SUCCESS(f'Posición YPFD creada: {bulk_positions["YPFD"].id}'))

        buys_total = sells_total = 0
        new_buys = new_sells = 0
        for i in range(BULK_PAIRS):
            ticker = BULK_TICKERS[i % len(BULK_TICKERS)]
            pos = bulk_positions[ticker]
            buy_day, sell_day = schedule[i * 2], schedule[i * 2 + 1]
            buy_price = BULK_BASE_PRICE + i * BULK_PRICE_STEP
            sell_price = buy_price + BULK_SELL_SPREAD

            buy_exists = Lot.objects.filter(
                position=pos, amount=BULK_BUY_AMOUNT,
                price_local=buy_price, purchased_at__date=buy_day,
            ).exists()
            if buy_exists:
                buys_total += 1
            else:
                lot_manager.add_lot(
                    pos.id, BULK_BUY_AMOUNT, buy_price, aware_at(buy_day), 'ARS', 0,
                    price_input_currency='ARS', manual_ccl_rate=ccl,
                )
                buys_total += 1
                new_buys += 1

            sell_exists = Sale.objects.filter(
                position=pos, amount=BULK_SELL_AMOUNT,
                price_local=sell_price, sold_at__date=sell_day,
            ).exists()
            if not sell_exists:
                sale_manager.add_sale(
                    pos.id, BULK_SELL_AMOUNT, sell_price, aware_at(sell_day), 'ARS',
                    price_input_currency='ARS', manual_ccl_rate=ccl,
                )
                sells_total += 1
                new_sells += 1
            else:
                sells_total += 1
        self.stdout.write(self.style.SUCCESS(
            f'Movimientos masivos: {buys_total} compras ({new_buys} nuevas), '
            f'{sells_total} ventas ({new_sells} nuevas).'
        ))

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
