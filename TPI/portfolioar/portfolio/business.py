from decimal import Decimal
from datetime import timedelta
import math
import requests
from django.utils import timezone

from . import fifo
from .data_access import (
    get_positions_by_user, get_position_by_id, create_position,
    delete_position, update_position_status,
    get_lots_by_position, get_lot_by_id, create_lot, delete_lot,
    get_sale_lots_for_lots, create_sale, create_sale_lot,
    get_sales_by_position, get_sale_by_id,
    get_stock_price_from_iol, get_sp500_return, get_historical_prices,
    get_cash_positions_by_user, get_cash_position_by_id,
    create_cash_position, update_cash_position, delete_cash_position,
    get_ccl_rate, get_cash_transactions_by_user,
    get_cash_transaction_by_lot, create_cash_transaction,
)


def _fetch_open_lots(position_id):
    lots = list(get_lots_by_position(position_id))
    lot_ids = [lot.id for lot in lots]
    sale_lots = list(get_sale_lots_for_lots(lot_ids)) if lot_ids else []
    return fifo.get_open_lots(lots, sale_lots)


def sync_position_status(position_id):
    open_lots = _fetch_open_lots(position_id)
    total_open = sum(remaining for _, remaining in open_lots)
    update_position_status(position_id, 'open' if total_open > 0 else 'closed')


class ExternalAPIs:
    @staticmethod
    def get_indec_inflation(start_date, end_date):
        try:
            url = "https://apis.datos.gob.ar/series/api/series/"
            params = {
                'ids': '148.3_INIVELNAL_DICI_M_26',
                'start_date': start_date.strftime('%Y-%m'),
                'end_date': end_date.strftime('%Y-%m'),
                'format': 'json'
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                series = data.get('data', [])
                if len(series) >= 2:
                    start_index = Decimal(str(series[0][1]))
                    end_index = Decimal(str(series[-1][1]))
                    if start_index > 0:
                        return (end_index / start_index - 1) * 100
            return Decimal('0')
        except Exception:
            return Decimal('0')

    @staticmethod
    def get_sp500_performance(start_date, end_date):
        try:
            result = get_sp500_return(start_date, end_date)
            if result is not None:
                return Decimal(str(round(result, 4)))
            return Decimal('0')
        except Exception:
            return Decimal('0')

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

    def add_position(self, user_id, stock_id, broker_id, amount, price_local, price_usd, purchased_at, purchase_currency='ARS', fees=0):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if price_local <= 0 or price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        if purchase_currency not in ('ARS', 'USD'):
            raise ValueError("La moneda debe ser ARS o USD")

        cash_manager = CashManager()
        cost = Decimal(str(amount)) * Decimal(str(price_local if purchase_currency == 'ARS' else price_usd))

        available = cash_manager.get_available(user_id, purchase_currency)
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
        if get_sales_by_position(position_id).exists():
            raise ValueError("No se puede eliminar una posición que ya tiene ventas registradas")

        for lot in get_lots_by_position(position_id):
            buy_tx = get_cash_transaction_by_lot(lot.id, tipo='compra')
            if buy_tx:
                create_cash_transaction(
                    buy_tx.user_id, buy_tx.currency, buy_tx.amount, 'recupero',
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

        if open_amount == 0:
            invested_amount = Decimal('0')
            current_value = Decimal('0')
            profit_loss = Decimal('0')
            profit_loss_percentage = Decimal('0')
        else:
            invested_amount = avg_cost_local * open_amount
            current_price = self.external_apis.get_current_price(position.stock.ticker) or avg_cost_local
            current_value = current_price * open_amount
            profit_loss = current_value - invested_amount
            profit_loss_percentage = (profit_loss / invested_amount * 100) if invested_amount > 0 else Decimal('0')

        days_held = (timezone.now() - position.opened_at).days if position.opened_at else 0
        years_held = Decimal(str(days_held)) / Decimal('365')
        annualized_return = (profit_loss_percentage / years_held) if years_held > 0 else Decimal('0')

        sales = get_sales_by_position(position.id)
        realized_pnl_ars = sum((s.realized_pnl_ars for s in sales), Decimal('0'))
        realized_pnl_usd = sum((s.realized_pnl_usd for s in sales), Decimal('0'))

        return {
            'open_amount': open_amount,
            'avg_cost_local': avg_cost_local,
            'avg_cost_usd': avg_cost_usd,
            'invested_amount': invested_amount,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            'annualized_return': annualized_return,
            'days_held': days_held,
            'realized_pnl_ars': realized_pnl_ars,
            'realized_pnl_usd': realized_pnl_usd,
            'total_pnl_ars': profit_loss + realized_pnl_ars,
        }

    def compare_with_sp500(self, position):
        if not position.opened_at:
            return {'sp500_return': Decimal('0'), 'alpha': Decimal('0')}

        sp500_return = self.external_apis.get_sp500_performance(
            position.opened_at.date(),
            timezone.now().date()
        )

        performance = self.calculate_position_performance(position)
        alpha = performance['profit_loss_percentage'] - sp500_return

        return {
            'sp500_return': sp500_return,
            'alpha': alpha
        }

    def compare_with_inflation(self, position):
        if not position.opened_at:
            return {'inflation': Decimal('0'), 'real_return': Decimal('0')}

        inflation = self.external_apis.get_indec_inflation(
            position.opened_at.date(),
            timezone.now().date()
        )

        performance = self.calculate_position_performance(position)
        real_return = performance['profit_loss_percentage'] - inflation

        return {
            'inflation': inflation,
            'real_return': real_return
        }

    def calculate_portfolio_summary(self, user_id):
        positions = get_positions_by_user(user_id)

        total_invested = Decimal('0')
        total_current_value = Decimal('0')
        total_realized_pnl_ars = Decimal('0')
        open_position_count = 0
        sector_distribution = {}

        for position in positions:
            performance = self.calculate_position_performance(position)
            total_invested += performance['invested_amount']
            total_current_value += performance['current_value']
            total_realized_pnl_ars += performance['realized_pnl_ars']

            if performance['open_amount'] > 0:
                open_position_count += 1
                sector = position.stock.sector.name if position.stock.sector else 'Sin sector'
                sector_distribution.setdefault(sector, Decimal('0'))
                sector_distribution[sector] += performance['invested_amount']

        profit_loss = total_current_value - total_invested
        profit_loss_percentage = (profit_loss / total_invested * 100) if total_invested > 0 else Decimal('0')

        total_sp500_return = self.external_apis.get_sp500_performance(
            timezone.now().date() - timedelta(days=365),
            timezone.now().date()
        )
        alpha = profit_loss_percentage - total_sp500_return

        total_inflation = self.external_apis.get_indec_inflation(
            timezone.now().date() - timedelta(days=365),
            timezone.now().date()
        )
        real_return = profit_loss_percentage - total_inflation

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
            import pandas_ta as ta
            df = get_historical_prices(position.stock.ticker)
            if df is None or len(df) < 30:
                raise ValueError("datos insuficientes")

            rsi_s = ta.rsi(df['Close'], length=14)
            macd_df = ta.macd(df['Close'])
            sma_20 = ta.sma(df['Close'], length=20)
            sma_50 = ta.sma(df['Close'], length=50)
            ema_30 = ta.ema(df['Close'], length=30)

            avg_vol = float(df['Volume'].mean())
            vol_relative = float(df['Volume'].iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
            volatility = float(df['Close'].pct_change().dropna().std()) * (252 ** 0.5) * 100

            def d(val):
                f = float(val)
                return Decimal(str(round(f, 4))) if not (math.isnan(f) or math.isinf(f)) else Decimal('0')

            return {
                'rsi': d(rsi_s.iloc[-1]),
                'macd': d(macd_df['MACD_12_26_9'].iloc[-1]),
                'macd_signal': d(macd_df['MACDs_12_26_9'].iloc[-1]),
                'macd_histogram': d(macd_df['MACDh_12_26_9'].iloc[-1]),
                'sma_20': d(sma_20.iloc[-1]),
                'sma_50': d(sma_50.iloc[-1]),
                'ema_30': d(ema_30.iloc[-1]),
                'volume_relative': Decimal(str(round(vol_relative, 4))),
                'volatility': Decimal(str(round(volatility, 4))),
            }
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


class LotManager:
    def get_position_lots(self, position_id):
        return get_lots_by_position(position_id)

    def get_lot(self, lot_id, user_id=None):
        return get_lot_by_id(lot_id, user_id)

    def add_lot(self, position_id, amount, price_local, price_usd, purchased_at, purchase_currency='ARS', fees=0):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if price_local <= 0 or price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        if purchase_currency not in ('ARS', 'USD'):
            raise ValueError("La moneda debe ser ARS o USD")

        position = get_position_by_id(position_id)
        cash_manager = CashManager()
        cost = Decimal(str(amount)) * Decimal(str(price_local if purchase_currency == 'ARS' else price_usd))

        available = cash_manager.get_available(position.user_id, purchase_currency)
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
        if get_sale_lots_for_lots([lot_id]).exists():
            raise ValueError("No se puede eliminar un lote que ya fue vendido, total o parcialmente")

        lot = get_lot_by_id(lot_id)
        position_id = lot.position_id
        buy_tx = get_cash_transaction_by_lot(lot_id, tipo='compra')
        if buy_tx:
            create_cash_transaction(
                buy_tx.user_id, buy_tx.currency, buy_tx.amount, 'recupero',
                position_id=position_id, lot_id=lot_id
            )
        delete_lot(lot_id)
        sync_position_status(position_id)


class SaleManager:
    def get_position_sales(self, position_id):
        return get_sales_by_position(position_id)

    def get_sale(self, sale_id, user_id=None):
        return get_sale_by_id(sale_id, user_id)

    def add_sale(self, position_id, amount, price_local, price_usd, sold_at, sell_currency='ARS'):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if price_local <= 0 or price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        if sell_currency not in ('ARS', 'USD'):
            raise ValueError("La moneda debe ser ARS o USD")

        position = get_position_by_id(position_id)
        open_lots = _fetch_open_lots(position_id)
        consumptions = fifo.compute_sale_consumption(open_lots, amount)
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
        create_cash_transaction(position.user_id, sell_currency, proceeds, 'recupero', position_id=position_id, sale_id=sale.id)

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

    def get_available(self, user_id, currency):
        positions = get_cash_positions_by_user(user_id)
        total = sum(c.amount for c in positions if c.currency == currency)
        transactions = get_cash_transactions_by_user(user_id)
        compras = sum(t.amount for t in transactions if t.currency == currency and t.tipo == 'compra')
        recuperos = sum(t.amount for t in transactions if t.currency == currency and t.tipo == 'recupero')
        return total - compras + recuperos

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
