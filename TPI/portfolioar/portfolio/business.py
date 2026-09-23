from decimal import Decimal
from datetime import datetime, timedelta
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
)


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


def _resolve_lot_prices(price, currency):
    price = Decimal(str(price))
    if not price.is_finite() or price <= 0:
        raise ValueError("El precio debe ser mayor a 0")
    if currency not in ('ARS', 'USD'):
        raise ValueError("La moneda debe ser ARS o USD")

    try:
        ccl = Decimal(str(get_ccl_rate()))
    except Exception as error:
        raise ValueError("No se pudo obtener el tipo de cambio para validar el precio, intentá de nuevo") from error
    if not ccl.is_finite() or ccl <= 0:
        raise ValueError("No se pudo obtener el tipo de cambio para validar el precio, intentá de nuevo")

    if currency == 'ARS':
        return price, price / ccl
    return price * ccl, price


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

    def add_position(self, user_id, stock_id, broker_id, amount, price, purchased_at, purchase_currency='ARS', fees=0):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        purchased_at = _validate_operation_datetime(purchased_at, 'compra')
        price_local, price_usd = _resolve_lot_prices(price, purchase_currency)

        cash_manager = CashManager()
        cost = Decimal(str(amount)) * Decimal(str(price_local if purchase_currency == 'ARS' else price_usd))

        with transaction.atomic():
            available = cash_manager.get_available(user_id, purchase_currency, for_update=True)
            if available < cost:
                symbol = '$' if purchase_currency == 'ARS' else 'U$D'
                raise ValueError(
                    f"Liquidez insuficiente en {purchase_currency}. "
                    f"Disponible: {symbol}{available:,.2f} — Requerido: {symbol}{cost:,.2f}"
                )

            position = create_position(user_id, stock_id, broker_id, opened_at=purchased_at, status='open')
            lot = create_lot(position.id, amount, price_local, price_usd, purchased_at, purchase_currency, fees)
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
            invested_amount = avg_cost_local * open_amount
            invested_amount_usd = avg_cost_usd * open_amount
            current_price = self.external_apis.get_current_price(position.stock.ticker)
            comparison_start = fifo.compute_weighted_purchase_date(open_lots)
            comparison_end = timezone.now()

            if current_price is None:
                current_value = None
                profit_loss = None
                profit_loss_percentage = None
            else:
                current_value = current_price * open_amount
                profit_loss = current_value - invested_amount
                profit_loss_percentage = (profit_loss / invested_amount * 100) if invested_amount > 0 else None
                try:
                    ccl = Decimal(str(get_ccl_rate()))
                    if ccl <= 0:
                        raise ValueError('CCL inválido')
                    current_value_usd = (current_price / ccl) * open_amount
                    profit_loss_percentage_usd = (
                        (current_value_usd - invested_amount_usd) / invested_amount_usd * 100
                        if invested_amount_usd > 0 else None
                    )
                except Exception:
                    pass
        else:
            sale_lots = list(get_sale_lots_by_position(position.id))
            invested_amount = sum(
                (Decimal(str(sale_lot.amount_consumed)) * sale_lot.cost_price_local for sale_lot in sale_lots),
                Decimal('0'),
            )
            invested_amount_usd = sum(
                (Decimal(str(sale_lot.amount_consumed)) * sale_lot.cost_price_usd for sale_lot in sale_lots),
                Decimal('0'),
            )
            current_value = invested_amount + realized_pnl_ars if invested_amount > 0 else None
            current_value_usd = invested_amount_usd + realized_pnl_usd if invested_amount_usd > 0 else None
            profit_loss = realized_pnl_ars if invested_amount > 0 else None
            profit_loss_percentage = (
                realized_pnl_ars / invested_amount * 100 if invested_amount > 0 else None
            )
            profit_loss_percentage_usd = (
                realized_pnl_usd / invested_amount_usd * 100 if invested_amount_usd > 0 else None
            )
            realized_return_percentage = profit_loss_percentage
            comparison_start = fifo.compute_weighted_consumed_purchase_date(sale_lots)
            comparison_end = fifo.compute_weighted_sale_date(sales)

        days_held = (
            (comparison_end - comparison_start).days
            if comparison_start is not None and comparison_end is not None else None
        )
        years_held = Decimal(str(days_held)) / Decimal('365') if days_held is not None else None
        annualized_return = self._calculate_cagr(invested_amount, current_value, years_held)

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
            'total_pnl_ars': profit_loss + realized_pnl_ars if profit_loss is not None else None,
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
        nominal_return = performance['profit_loss_percentage']
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
            total_invested += performance['invested_amount'] or Decimal('0')
            if performance['current_value'] is None:
                has_unavailable_price = True
            else:
                total_current_value += performance['current_value']
            total_realized_pnl_ars += performance['realized_pnl_ars']

            if performance['open_amount'] > 0:
                open_position_count += 1
                sector = position.stock.sector.name if position.stock.sector else 'Sin sector'
                sector_distribution.setdefault(sector, Decimal('0'))
                sector_distribution[sector] += performance['invested_amount']

        if has_unavailable_price:
            total_current_value = None
            profit_loss = None
            profit_loss_percentage = None
        else:
            profit_loss = total_current_value - total_invested
            profit_loss_percentage = (profit_loss / total_invested * 100) if total_invested > 0 else Decimal('0')

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

    def add_lot(self, position_id, amount, price, purchased_at, purchase_currency='ARS', fees=0):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        purchased_at = _validate_operation_datetime(purchased_at, 'compra')
        price_local, price_usd = _resolve_lot_prices(price, purchase_currency)

        cash_manager = CashManager()
        cost = Decimal(str(amount)) * Decimal(str(price_local if purchase_currency == 'ARS' else price_usd))

        with transaction.atomic():
            position = get_position_for_update(position_id)
            available = cash_manager.get_available(position.user_id, purchase_currency, for_update=True)
            if available < cost:
                symbol = '$' if purchase_currency == 'ARS' else 'U$D'
                raise ValueError(
                    f"Liquidez insuficiente en {purchase_currency}. "
                    f"Disponible: {symbol}{available:,.2f} — Requerido: {symbol}{cost:,.2f}"
                )

            lot = create_lot(position_id, amount, price_local, price_usd, purchased_at, purchase_currency, fees)
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

    def add_sale(self, position_id, amount, price, sold_at, sell_currency='ARS'):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        price_local, price_usd = _resolve_lot_prices(price, sell_currency)
        sold_at = _validate_operation_datetime(sold_at, 'venta')

        with transaction.atomic():
            position = get_position_for_update(position_id)
            open_lots = _fetch_open_lots(position_id, for_update=True)
            consumptions = fifo.compute_sale_consumption(open_lots, amount)
            earliest_purchase = min(consumption.lot.purchased_at for consumption in consumptions)
            if sold_at < earliest_purchase:
                raise ValueError("La fecha de venta no puede ser anterior a la compra de los lotes vendidos")
            realized_pnl_ars, realized_pnl_usd, _, _ = fifo.compute_realized_pnl(consumptions, price_local, price_usd)

            sale = create_sale(
                position_id, amount, price_local, price_usd, sold_at, sell_currency,
                realized_pnl_ars, realized_pnl_usd
            )
            for consumption in consumptions:
                create_sale_lot(
                    sale.id, consumption.lot.id, consumption.amount_consumed,
                    consumption.cost_price_local, consumption.cost_price_usd
                )

            proceeds = Decimal(str(amount)) * Decimal(str(price_local if sell_currency == 'ARS' else price_usd))
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
            'ccl': ccl,
            'total_ars_equivalent': total_ars_equivalent,
        }
