from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, time
import math
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import fifo
from .data_access import (
    get_positions_by_user, get_position_by_id, get_position_for_update, create_position,
    delete_position, update_position_status,
    get_lots_by_position, get_lots_by_position_for_update,
    get_lot_by_id, get_lot_for_update, create_lot, delete_lot,
    get_sale_lots_for_lots, get_sale_lots_by_position, create_sale, create_sale_lot,
    get_sales_by_position, get_sale_by_id,
    get_stock_price_from_iol, get_sp500_return, get_historical_prices, get_indec_inflation_series,
    get_cash_positions_by_user, get_cash_positions_by_user_for_update, get_cash_position_by_id,
    create_cash_position, update_cash_position, delete_cash_position,
    get_ccl_rate, get_cash_transactions_by_user,
    get_cash_transaction_by_lot, create_cash_transaction,
    get_iol_quote, get_iol_daily_series, get_historical_ccl, get_holidays,
)
from core.business import StockManager


PRICE_PRECISION = Decimal('0.0001')


@dataclass(frozen=True)
class QuoteResult:
    price: Decimal
    currency: str
    quote_date: object
    source: str
    observed_at: object = None


@dataclass(frozen=True)
class CclResult:
    rate: Decimal
    ccl_date: object
    source: str = 'argentinadatos'
    side: str = 'venta'


@dataclass(frozen=True)
class PricingSnapshot:
    price_local: Decimal
    price_usd: Decimal
    price_input_currency: str
    price_origin: str
    price_source: str
    price_quote_date: object
    quote_currency: str | None
    quote_unit: int
    ccl_rate: Decimal
    ccl_date: object
    ccl_source: str


class ManualCclRequired(ValueError):
    """La cotización puede guardarse, pero el usuario debe confirmar un CCL manual."""


def _operation_day(operation_dt):
    if settings.USE_TZ and timezone.is_aware(operation_dt):
        return timezone.localtime(operation_dt, timezone.get_current_timezone()).date()
    return operation_dt.date()


def is_business_day(day):
    if day.weekday() >= 5:
        return False
    try:
        holidays = get_holidays(day.year)
    except Exception:
        holidays = None
    if holidays is None:
        return True
    return str(day) not in {item.get('fecha') for item in holidays}


def last_business_day(reference):
    day = reference
    while not is_business_day(day):
        day -= timedelta(days=1)
    return day


def default_operation_datetime():
    now = timezone.now()
    today = timezone.localdate() if settings.USE_TZ else now.date()
    day = last_business_day(today)
    value = datetime.combine(day, time(17, 0))
    if settings.USE_TZ:
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def validate_business_day(operation_dt):
    day = _operation_day(operation_dt)
    if not is_business_day(day):
        raise ValueError(f"El {day:%d/%m/%Y} no es día hábil bursátil")
    return day


def _fetch_open_lots(position_id, for_update=False):
    lots_query = get_lots_by_position_for_update if for_update else get_lots_by_position
    lots = list(lots_query(position_id))
    lot_ids = [lot.id for lot in lots]
    sale_lots = list(get_sale_lots_for_lots(lot_ids)) if lot_ids else []
    return fifo.get_open_lots(lots, sale_lots)


def sync_position_status(position_id):
    open_lots = _fetch_open_lots(position_id)
    total_open = sum(remaining for _, remaining in open_lots)
    update_position_status(position_id, 'open' if total_open > 0 else 'closed')


def _validate_operation_datetime(value, field_name):
    if not isinstance(value, datetime):
        raise ValueError(f"La fecha de {field_name} es inválida")

    if settings.USE_TZ and timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    elif not settings.USE_TZ and timezone.is_aware(value):
        value = timezone.make_naive(value, timezone.get_current_timezone())

    if value > timezone.now():
        raise ValueError(f"La fecha de {field_name} no puede estar en el futuro")
    return value


class MarketDataManager:
    @staticmethod
    def _currency(value):
        normalized = str(value or '').lower()
        if 'dolar' in normalized or normalized == 'usd':
            return 'USD'
        return 'ARS'

    def get_quote_for_date(self, stock, day):
        today = timezone.localdate() if settings.USE_TZ else timezone.now().date()
        try:
            if day == today:
                raw = get_iol_quote(stock.ticker)
                price = raw.get('ultimoPrecio')
                if price is None:
                    return None, 'sin_datos'
                return QuoteResult(
                    Decimal(str(price)), self._currency(raw.get('moneda')), day,
                    'iol_realtime', raw.get('fechaHora'),
                ), None

            rows = get_iol_daily_series(stock.ticker, day, day + timedelta(days=1))
            if not rows:
                return None, 'sin_datos'
            raw = rows[0]
            price = raw.get('ultimoPrecio')
            if price is None:
                return None, 'sin_datos'
            return QuoteResult(
                Decimal(str(price)), self._currency(raw.get('moneda')), day,
                'iol_daily_close', raw.get('fechaHora'),
            ), None
        except Exception:
            return None, 'fuente_no_disponible'

    def get_ccl_for_date(self, day):
        try:
            raw = get_historical_ccl(day)
            if not raw:
                return None, 'sin_datos'
            rate = raw.get('venta')
            if rate is None:
                return None, 'sin_datos'
            rate = Decimal(str(rate))
            if not rate.is_finite() or rate <= 0:
                return None, 'sin_datos'
            return CclResult(rate, day), None
        except Exception:
            return None, 'fuente_no_disponible'

    def resolve_operation_pricing(
        self, stock, operation_dt, price, price_input_currency,
        client_ccl_rate=None, manual_ccl_rate=None,
    ):
        price = Decimal(str(price))
        if not price.is_finite() or price <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        if price_input_currency not in ('ARS', 'USD'):
            raise ValueError("La moneda del precio debe ser ARS o USD")

        day = validate_business_day(operation_dt)
        quote, _ = self.get_quote_for_date(stock, day)
        ccl, _ = self.get_ccl_for_date(day)
        if ccl is None:
            try:
                manual_rate = Decimal(str(manual_ccl_rate))
            except Exception as error:
                raise ManualCclRequired("Ingresá el CCL manual para la fecha de operación") from error
            if not manual_rate.is_finite() or manual_rate <= 0:
                raise ManualCclRequired("Ingresá un CCL manual mayor a 0")
            ccl = CclResult(manual_rate, day, source='manual')

        if client_ccl_rate not in (None, ''):
            seen_rate = Decimal(str(client_ccl_rate))
            if seen_rate > 0 and abs(ccl.rate - seen_rate) / seen_rate > Decimal('0.005'):
                raise ValueError("El CCL cambió más de 0,5%. Revisá los importes y confirmá nuevamente")

        if price_input_currency == 'ARS':
            price_local = price
            price_usd = (price / ccl.rate).quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)
        else:
            price_usd = price
            price_local = (price * ccl.rate).quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)

        expected_input_price = None
        if quote is not None:
            expected_input_price = quote.price
            if quote.currency != price_input_currency:
                expected_input_price = (
                    quote.price * ccl.rate if price_input_currency == 'ARS'
                    else quote.price / ccl.rate
                )
        quote_matches_input = (
            expected_input_price is not None
            and expected_input_price.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)
            == price.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP)
        )
        return PricingSnapshot(
            price_local=price_local,
            price_usd=price_usd,
            price_input_currency=price_input_currency,
            price_origin='auto' if quote_matches_input else 'manual',
            price_source=quote.source if quote_matches_input else 'manual',
            price_quote_date=quote.quote_date if quote_matches_input else None,
            quote_currency=quote.currency if quote_matches_input else None,
            quote_unit=StockManager().get_quote_unit(stock),
            ccl_rate=ccl.rate.quantize(PRICE_PRECISION, rounding=ROUND_HALF_UP),
            ccl_date=ccl.ccl_date,
            ccl_source=ccl.source,
        )


class ExternalAPIs:
    @staticmethod
    def get_indec_inflation(start_date, end_date):
        try:
            series = get_indec_inflation_series(start_date, end_date)
            if len(series) < 2:
                return None
            start_index = Decimal(str(series[0][1]))
            end_index = Decimal(str(series[-1][1]))
            if start_index > 0:
                return (end_index / start_index - 1) * 100
            return None
        except Exception:
            return None

    @staticmethod
    def get_sp500_performance(start_date, end_date):
        try:
            result = get_sp500_return(start_date, end_date)
            if result is not None and math.isfinite(result):
                return Decimal(str(round(result, 4)))
            return None
        except Exception:
            return None

    @staticmethod
    def get_current_price(ticker, mercado='bCBA'):
        try:
            price = get_stock_price_from_iol(ticker, mercado)
            if price is not None:
                return Decimal(str(price))
            return None
        except Exception:
            return None


class PortfolioManager:
    def __init__(self):
        self.external_apis = ExternalAPIs()

    def get_user_positions(self, user_id):
        return get_positions_by_user(user_id)

    def get_position(self, position_id, user_id=None):
        return get_position_by_id(position_id, user_id)

    def add_position(
        self, user_id, stock_id, broker_id, amount, price, purchased_at, purchase_currency='ARS', fees=0,
        price_input_currency=None, client_ccl_rate=None, manual_ccl_rate=None,
    ):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        purchased_at = _validate_operation_datetime(purchased_at, 'compra')
        stock = StockManager().get_by_id(stock_id)
        pricing = MarketDataManager().resolve_operation_pricing(
            stock, purchased_at, price, price_input_currency or purchase_currency,
            client_ccl_rate, manual_ccl_rate,
        )

        cash_manager = CashManager()
        paid_price = pricing.price_local if purchase_currency == 'ARS' else pricing.price_usd
        cost = Decimal(str(amount)) * paid_price / pricing.quote_unit

        with transaction.atomic():
            available = cash_manager.get_available(user_id, purchase_currency, for_update=True)
            if available < cost:
                symbol = '$' if purchase_currency == 'ARS' else 'U$D'
                raise ValueError(
                    f"Liquidez insuficiente en {purchase_currency}. "
                    f"Disponible: {symbol}{available:,.2f} — Requerido: {symbol}{cost:,.2f}"
                )

            position = create_position(user_id, stock_id, broker_id, opened_at=purchased_at, status='open')
            lot = create_lot(
                position.id, amount, pricing.price_local, pricing.price_usd, purchased_at,
                purchase_currency, fees, pricing,
            )
            create_cash_transaction(user_id, purchase_currency, cost, 'compra', position_id=position.id, lot_id=lot.id)
        return position

    def remove_position(self, position_id):
        with transaction.atomic():
            get_position_for_update(position_id)
            if get_sales_by_position(position_id).exists():
                raise ValueError("No se puede eliminar una posición que ya tiene ventas registradas")

            for lot in get_lots_by_position_for_update(position_id):
                buy_tx = get_cash_transaction_by_lot(lot.id, tipo='compra')
                if buy_tx:
                    create_cash_transaction(
                        buy_tx.user_id, buy_tx.currency, buy_tx.amount, 'reembolso',
                        position_id=position_id, lot_id=lot.id
                    )
            delete_position(position_id)

    def get_lots_with_remaining(self, position_id):
        lots = list(get_lots_by_position(position_id))
        lot_ids = [lot.id for lot in lots]
        sale_lots = list(get_sale_lots_for_lots(lot_ids)) if lot_ids else []
        consumed = {}
        for sl in sale_lots:
            consumed[sl.lot_id] = consumed.get(sl.lot_id, 0) + sl.amount_consumed
        return [(lot, lot.amount - consumed.get(lot.id, 0)) for lot in lots]

    def get_open_position_summary(self, position):
        open_lots = _fetch_open_lots(position.id)
        avg_cost_local, avg_cost_usd, open_amount = fifo.compute_weighted_avg_cost(open_lots)
        return {
            'open_amount': open_amount,
            'avg_cost_local': avg_cost_local,
            'avg_cost_usd': avg_cost_usd,
        }

    def _fallback_price(self, position):
        open_lots = _fetch_open_lots(position.id)
        avg_cost_local, _, open_amount = fifo.compute_weighted_avg_cost(open_lots)
        if open_amount > 0:
            return avg_cost_local
        lots = list(get_lots_by_position(position.id))
        if lots:
            return Decimal(str(lots[-1].price_local))
        return Decimal('0')

    def calculate_position_performance(self, position):
        open_lots = _fetch_open_lots(position.id)
        avg_cost_local, avg_cost_usd, open_amount = fifo.compute_weighted_avg_cost(open_lots)
        sales = list(get_sales_by_position(position.id))
        realized_pnl_ars = sum((sale.realized_pnl_ars for sale in sales), Decimal('0'))
        realized_pnl_usd = sum((sale.realized_pnl_usd for sale in sales), Decimal('0'))

        invested_amount_usd = None
        current_value_usd = None
        profit_loss_percentage_usd = None
        realized_return_percentage = None

        if open_amount > 0:
            quote_unit = open_lots[0][0].quote_unit
            invested_amount = avg_cost_local * open_amount / quote_unit
            invested_amount_usd = avg_cost_usd * open_amount / quote_unit
            current_price = self.external_apis.get_current_price(position.stock.ticker)
            comparison_start = fifo.compute_weighted_purchase_date(open_lots)
            comparison_end = timezone.now()

            if current_price is None:
                current_value = None
                profit_loss = None
                profit_loss_percentage = None
            else:
                current_value = current_price * open_amount / quote_unit
                profit_loss = current_value - invested_amount
                profit_loss_percentage = (profit_loss / invested_amount * 100) if invested_amount > 0 else None
                try:
                    ccl = Decimal(str(get_ccl_rate()))
                    if ccl <= 0:
                        raise ValueError('CCL inválido')
                    current_value_usd = (current_price / ccl) * open_amount / quote_unit
                    profit_loss_percentage_usd = (
                        (current_value_usd - invested_amount_usd) / invested_amount_usd * 100
                        if invested_amount_usd > 0 else None
                    )
                except Exception:
                    pass
        else:
            # Posición cerrada: no hay acciones abiertas, así que no existe "valor actual"
            # ni P&L no realizado (eso ya se liquidó y volvió como liquidez vía CashManager).
            # Si acá se devolviera current_value = invested_amount + realized_pnl_ars, el
            # dashboard sumaría esa plata dos veces: una como liquidez y otra como "inversión".
            sale_lots = list(get_sale_lots_by_position(position.id))
            invested_amount = sum(
                (
                    Decimal(str(sale_lot.amount_consumed)) * sale_lot.cost_price_local / sale_lot.lot.quote_unit
                    for sale_lot in sale_lots
                ),
                Decimal('0'),
            )
            invested_amount_usd = sum(
                (
                    Decimal(str(sale_lot.amount_consumed)) * sale_lot.cost_price_usd / sale_lot.lot.quote_unit
                    for sale_lot in sale_lots
                ),
                Decimal('0'),
            )
            current_value = None
            current_value_usd = None
            profit_loss = None
            profit_loss_percentage = None
            profit_loss_percentage_usd = (
                realized_pnl_usd / invested_amount_usd * 100 if invested_amount_usd > 0 else None
            )
            realized_return_percentage = (
                realized_pnl_ars / invested_amount * 100 if invested_amount > 0 else None
            )
            comparison_start = fifo.compute_weighted_consumed_purchase_date(sale_lots)
            comparison_end = fifo.compute_weighted_sale_date(sales)

        days_held = (
            (comparison_end - comparison_start).days
            if comparison_start is not None and comparison_end is not None else None
        )
        years_held = Decimal(str(days_held)) / Decimal('365') if days_held is not None else None
        # Para CAGR de una posición cerrada usamos el valor final "de bolsillo" (costo + P&L
        # realizado), no current_value: ese queda en None a propósito para no duplicar la
        # liquidez ya recuperada en el total del portfolio.
        final_value_for_cagr = (
            current_value if open_amount > 0
            else (invested_amount + realized_pnl_ars if invested_amount is not None else None)
        )
        annualized_return = self._calculate_cagr(invested_amount, final_value_for_cagr, years_held)
        total_pnl_ars = (
            None if (open_amount > 0 and profit_loss is None)
            else (profit_loss or Decimal('0')) + realized_pnl_ars
        )

        return {
            'open_amount': open_amount,
            'avg_cost_local': avg_cost_local,
            'avg_cost_usd': avg_cost_usd,
            'invested_amount': invested_amount,
            'invested_amount_usd': invested_amount_usd,
            'current_value': current_value,
            'current_value_usd': current_value_usd,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            'profit_loss_percentage_usd': profit_loss_percentage_usd,
            'annualized_return': annualized_return,
            'days_held': days_held,
            'realized_pnl_ars': realized_pnl_ars,
            'realized_pnl_usd': realized_pnl_usd,
            'realized_return_percentage': realized_return_percentage,
            'comparison_start': comparison_start,
            'comparison_end': comparison_end,
            'price_unavailable': open_amount > 0 and current_value is None,
            'total_pnl_ars': total_pnl_ars,
        }

    # Extrapolar un retorno a un año completo cuando la posición se sostuvo apenas
    # unos días produce cifras astronómicas y sin sentido (p. ej. 600% en 5 días
    # anualizado da ~1e64%). Por debajo de este umbral no se anualiza.
    MIN_DAYS_FOR_ANNUALIZATION = 30

    @staticmethod
    def _calculate_cagr(initial_value, final_value, years):
        if initial_value is None or final_value is None or years is None or years <= 0:
            return None
        if years * 365 < PortfolioManager.MIN_DAYS_FOR_ANNUALIZATION:
            return None
        if initial_value <= 0 or final_value < 0:
            return None
        return ((final_value / initial_value) ** (Decimal('1') / years) - 1) * 100

    def compare_with_sp500(self, position, performance=None):
        if performance is None:
            performance = self.calculate_position_performance(position)
        start_date = performance['comparison_start']
        end_date = performance['comparison_end']
        if start_date is None or end_date is None:
            return {'sp500_return': None, 'alpha': None}

        sp500_return = self.external_apis.get_sp500_performance(
            start_date.date(),
            end_date.date()
        )
        position_return_usd = performance['profit_loss_percentage_usd']
        alpha = (
            position_return_usd - sp500_return
            if position_return_usd is not None and sp500_return is not None else None
        )

        return {
            'sp500_return': sp500_return,
            'alpha': alpha,
            'position_return_usd': position_return_usd,
        }

    def compare_with_inflation(self, position, performance=None):
        if performance is None:
            performance = self.calculate_position_performance(position)
        start_date = performance['comparison_start']
        end_date = performance['comparison_end']
        if start_date is None or end_date is None:
            return {'inflation': None, 'real_return': None}

        inflation = self.external_apis.get_indec_inflation(
            start_date.date(),
            end_date.date()
        )
        nominal_return = (
            performance['profit_loss_percentage'] if performance['open_amount'] > 0
            else performance['realized_return_percentage']
        )
        real_return = (
            ((Decimal('1') + nominal_return / 100) / (Decimal('1') + inflation / 100) - 1) * 100
            if nominal_return is not None and inflation is not None else None
        )

        return {
            'inflation': inflation,
            'real_return': real_return,
            'nominal_return': nominal_return,
        }

    def calculate_portfolio_summary(self, user_id):
        positions = get_positions_by_user(user_id)

        total_invested = Decimal('0')
        total_current_value = Decimal('0')
        total_realized_pnl_ars = Decimal('0')
        open_position_count = 0
        sector_distribution = {}
        has_unavailable_price = False

        for position in positions:
            performance = self.calculate_position_performance(position)
            total_realized_pnl_ars += performance['realized_pnl_ars']

            # Una posición cerrada no tiene invested_amount/current_value "vigentes": esa plata
            # ya está de vuelta en la liquidez (CashManager), sumarla acá la duplicaría en el
            # patrimonio total. Solo las posiciones abiertas aportan al valor de la cartera.
            if performance['open_amount'] > 0:
                open_position_count += 1
                total_invested += performance['invested_amount'] or Decimal('0')
                if performance['price_unavailable']:
                    has_unavailable_price = True
                else:
                    total_current_value += performance['current_value'] or Decimal('0')
                sector = position.stock.sector.name if position.stock.sector else 'Sin sector'
                sector_distribution.setdefault(sector, Decimal('0'))
                sector_distribution[sector] += performance['invested_amount']

        if has_unavailable_price:
            total_current_value = None
            profit_loss = None
            profit_loss_percentage = None
        else:
            profit_loss = (total_current_value - total_invested) + total_realized_pnl_ars
            profit_loss_percentage = (profit_loss / total_invested * 100) if total_invested > 0 else None

        total_sp500_return = self.external_apis.get_sp500_performance(
            timezone.now().date() - timedelta(days=365),
            timezone.now().date()
        )
        alpha = (
            profit_loss_percentage - total_sp500_return
            if profit_loss_percentage is not None and total_sp500_return is not None else None
        )

        total_inflation = self.external_apis.get_indec_inflation(
            timezone.now().date() - timedelta(days=365),
            timezone.now().date()
        )
        real_return = (
            ((Decimal('1') + profit_loss_percentage / 100) / (Decimal('1') + total_inflation / 100) - 1) * 100
            if profit_loss_percentage is not None and total_inflation is not None else None
        )

        return {
            'total_invested': total_invested,
            'total_current_value': total_current_value,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            'position_count': open_position_count,
            'sp500_return': total_sp500_return,
            'alpha': alpha,
            'inflation': total_inflation,
            'real_return': real_return,
            'sector_distribution': sector_distribution,
            'total_realized_pnl_ars': total_realized_pnl_ars,
        }

    def get_technical_indicators(self, position):
        try:
            df = get_historical_prices(position.stock.ticker)
            if df is None or len(df) < 30:
                raise ValueError("datos insuficientes")
            return self._calculate_technical_indicators(df)
        except Exception:
            price = self._fallback_price(position)
            return {
                'rsi': Decimal('0'),
                'macd': Decimal('0'),
                'macd_signal': Decimal('0'),
                'macd_histogram': Decimal('0'),
                'sma_20': price,
                'sma_50': price,
                'ema_30': price,
                'volume_relative': Decimal('1'),
                'volatility': Decimal('0'),
            }

    def get_alert_indicator_values(self, stock, required_keys=None):
        values = {}
        required_keys = set(required_keys) if required_keys is not None else None
        price_keys = {'precio', 'price'}
        technical_keys = {
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'sma_20', 'sma_50', 'ema_30', 'volume_relative',
            'volumen_relativo', 'volatility', 'volatilidad',
        }

        if required_keys is None or required_keys & price_keys:
            current_price = self.external_apis.get_current_price(stock.ticker)
            if current_price is not None:
                values['precio'] = current_price
                values['price'] = current_price

        if required_keys is None or required_keys & technical_keys:
            try:
                df = get_historical_prices(stock.ticker)
                if df is not None and len(df) >= 50:
                    values.update(self._calculate_technical_indicators(df))
            except Exception:
                pass

        if 'volume_relative' in values:
            values['volumen_relativo'] = values['volume_relative']
        if 'volatility' in values:
            values['volatilidad'] = values['volatility']
        return values

    @staticmethod
    def _calculate_technical_indicators(df):
        import pandas_ta as ta

        rsi_s = ta.rsi(df['Close'], length=14)
        macd_df = ta.macd(df['Close'])
        sma_20 = ta.sma(df['Close'], length=20)
        sma_50 = ta.sma(df['Close'], length=50)
        ema_30 = ta.ema(df['Close'], length=30)

        avg_vol = float(df['Volume'].mean())
        vol_relative = float(df['Volume'].iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
        volatility = float(df['Close'].pct_change().dropna().std()) * (252 ** 0.5) * 100

        def decimal_value(value):
            number = float(value)
            if math.isnan(number) or math.isinf(number):
                return Decimal('0')
            return Decimal(str(round(number, 4)))

        return {
            'rsi': decimal_value(rsi_s.iloc[-1]),
            'macd': decimal_value(macd_df['MACD_12_26_9'].iloc[-1]),
            'macd_signal': decimal_value(macd_df['MACDs_12_26_9'].iloc[-1]),
            'macd_histogram': decimal_value(macd_df['MACDh_12_26_9'].iloc[-1]),
            'sma_20': decimal_value(sma_20.iloc[-1]),
            'sma_50': decimal_value(sma_50.iloc[-1]),
            'ema_30': decimal_value(ema_30.iloc[-1]),
            'volume_relative': Decimal(str(round(vol_relative, 4))),
            'volatility': Decimal(str(round(volatility, 4))),
        }


class LotManager:
    def get_position_lots(self, position_id):
        return get_lots_by_position(position_id)

    def get_lot(self, lot_id, user_id=None):
        return get_lot_by_id(lot_id, user_id)

    def add_lot(
        self, position_id, amount, price, purchased_at, purchase_currency='ARS', fees=0,
        price_input_currency=None, client_ccl_rate=None, manual_ccl_rate=None,
    ):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        purchased_at = _validate_operation_datetime(purchased_at, 'compra')
        position = get_position_by_id(position_id)
        pricing = MarketDataManager().resolve_operation_pricing(
            position.stock, purchased_at, price, price_input_currency or purchase_currency,
            client_ccl_rate, manual_ccl_rate,
        )

        cash_manager = CashManager()
        paid_price = pricing.price_local if purchase_currency == 'ARS' else pricing.price_usd
        cost = Decimal(str(amount)) * paid_price / pricing.quote_unit

        with transaction.atomic():
            position = get_position_for_update(position_id)
            existing_units = {lot.quote_unit for lot in get_lots_by_position_for_update(position_id)}
            if existing_units and pricing.quote_unit not in existing_units:
                raise ValueError("La posición tiene lotes registrados en otra unidad")
            available = cash_manager.get_available(position.user_id, purchase_currency, for_update=True)
            if available < cost:
                symbol = '$' if purchase_currency == 'ARS' else 'U$D'
                raise ValueError(
                    f"Liquidez insuficiente en {purchase_currency}. "
                    f"Disponible: {symbol}{available:,.2f} — Requerido: {symbol}{cost:,.2f}"
                )

            lot = create_lot(
                position_id, amount, pricing.price_local, pricing.price_usd, purchased_at,
                purchase_currency, fees, pricing,
            )
            create_cash_transaction(position.user_id, purchase_currency, cost, 'compra', position_id=position_id, lot_id=lot.id)
            sync_position_status(position_id)
        return lot

    def remove_lot(self, lot_id):
        with transaction.atomic():
            lot = get_lot_for_update(lot_id)
            position_id = lot.position_id
            get_position_for_update(position_id)
            if get_sale_lots_for_lots([lot_id]).exists():
                raise ValueError("No se puede eliminar un lote que ya fue vendido, total o parcialmente")

            buy_tx = get_cash_transaction_by_lot(lot_id, tipo='compra')
            if buy_tx:
                create_cash_transaction(
                    buy_tx.user_id, buy_tx.currency, buy_tx.amount, 'reembolso',
                    position_id=position_id, lot_id=lot_id
                )
            delete_lot(lot_id)
            sync_position_status(position_id)


class SaleManager:
    def get_position_sales(self, position_id):
        return get_sales_by_position(position_id)

    def get_sale(self, sale_id, user_id=None):
        return get_sale_by_id(sale_id, user_id)

    def add_sale(
        self, position_id, amount, price, sold_at, sell_currency='ARS', price_input_currency=None,
        client_ccl_rate=None, manual_ccl_rate=None,
    ):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        sold_at = _validate_operation_datetime(sold_at, 'venta')
        position_for_pricing = get_position_by_id(position_id)
        pricing = MarketDataManager().resolve_operation_pricing(
            position_for_pricing.stock, sold_at, price, price_input_currency or sell_currency,
            client_ccl_rate, manual_ccl_rate,
        )

        with transaction.atomic():
            position = get_position_for_update(position_id)
            open_lots = _fetch_open_lots(position_id, for_update=True)
            consumptions = fifo.compute_sale_consumption(open_lots, amount)
            earliest_purchase = min(consumption.lot.purchased_at for consumption in consumptions)
            if sold_at < earliest_purchase:
                raise ValueError("La fecha de venta no puede ser anterior a la compra de los lotes vendidos")
            realized_pnl_ars, realized_pnl_usd, _, _ = fifo.compute_realized_pnl(
                consumptions, pricing.price_local, pricing.price_usd, pricing.quote_unit
            )

            sale = create_sale(
                position_id, amount, pricing.price_local, pricing.price_usd, sold_at, sell_currency,
                realized_pnl_ars, realized_pnl_usd, pricing
            )
            for consumption in consumptions:
                create_sale_lot(
                    sale.id, consumption.lot.id, consumption.amount_consumed,
                    consumption.cost_price_local, consumption.cost_price_usd
                )

            paid_price = pricing.price_local if sell_currency == 'ARS' else pricing.price_usd
            proceeds = Decimal(str(amount)) * paid_price / pricing.quote_unit
            create_cash_transaction(position.user_id, sell_currency, proceeds, 'venta', position_id=position_id, sale_id=sale.id)

            sync_position_status(position_id)
        return sale


class CashManager:
    def get_user_cash(self, user_id):
        return get_cash_positions_by_user(user_id)

    def get_cash(self, cash_id, user_id=None):
        return get_cash_position_by_id(cash_id, user_id)

    def add_cash(self, user_id, currency, amount, description=''):
        if amount <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        if currency not in ('ARS', 'USD'):
            raise ValueError("La moneda debe ser ARS o USD")
        return create_cash_position(user_id, currency, amount, description)

    def update_cash(self, cash_id, amount, description=''):
        if amount <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        return update_cash_position(cash_id, amount, description)

    def remove_cash(self, cash_id):
        delete_cash_position(cash_id)

    def get_available(self, user_id, currency, for_update=False):
        positions_query = get_cash_positions_by_user_for_update if for_update else get_cash_positions_by_user
        positions = positions_query(user_id)
        total = sum(c.amount for c in positions if c.currency == currency)
        transactions = get_cash_transactions_by_user(user_id)
        compras = sum(t.amount for t in transactions if t.currency == currency and t.tipo == 'compra')
        creditos = sum(
            t.amount for t in transactions
            if t.currency == currency and t.tipo in ('venta', 'reembolso')
        )
        return total - compras + creditos

    def get_totals(self, user_id):
        positions = get_cash_positions_by_user(user_id)
        total_ars = sum(c.amount for c in positions if c.currency == 'ARS')
        total_usd = sum(c.amount for c in positions if c.currency == 'USD')
        available_ars = self.get_available(user_id, 'ARS')
        available_usd = self.get_available(user_id, 'USD')
        try:
            ccl = Decimal(str(get_ccl_rate()))
            total_ars_equivalent = available_ars + available_usd * ccl
        except Exception:
            ccl = Decimal('0')
            total_ars_equivalent = available_ars
        return {
            'total_ars': total_ars,
            'total_usd': total_usd,
            'available_ars': available_ars,
            'available_usd': available_usd,
            'has_available_cash': available_ars > 0 or available_usd > 0,
            'ccl': ccl,
            'total_ars_equivalent': total_ars_equivalent,
        }
