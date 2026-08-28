from decimal import Decimal
from datetime import timedelta
import math
import requests
from django.utils import timezone

from .data_access import (
    get_positions_by_user, get_position_by_id, create_position,
    update_position, delete_position, get_orders_by_position,
    get_order_by_id, create_order, delete_order,
    get_stock_price_from_iol, get_sp500_return, get_historical_prices,
    get_cash_positions_by_user, get_cash_position_by_id,
    create_cash_position, update_cash_position, delete_cash_position,
    get_ccl_rate,
)


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

    def add_position(self, user_id, stock_id, broker_id, amount, stock_price_local, stock_price_usd, purchased_at):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if stock_price_local <= 0 or stock_price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")

        return create_position(user_id, stock_id, broker_id, amount, stock_price_local, stock_price_usd, purchased_at)

    def update_position(self, position_id, amount=None, stock_price_local=None, stock_price_usd=None):
        if amount is not None and amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if stock_price_local is not None and stock_price_local <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        if stock_price_usd is not None and stock_price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")

        return update_position(position_id, amount, stock_price_local, stock_price_usd)

    def remove_position(self, position_id):
        delete_position(position_id)

    def calculate_position_performance(self, position):
        buy_price = Decimal(str(position.stock_price_local))
        invested_amount = position.amount * buy_price
        current_price = self.external_apis.get_current_price(position.stock.ticker) or buy_price
        current_value = position.amount * current_price

        profit_loss = current_value - invested_amount
        profit_loss_percentage = (profit_loss / invested_amount * 100) if invested_amount > 0 else Decimal('0')

        days_held = (timezone.now() - position.purchased_at).days if position.purchased_at else 0
        years_held = Decimal(str(days_held)) / Decimal('365')
        annualized_return = ((profit_loss_percentage / years_held) if years_held > 0 else Decimal('0'))

        return {
            'invested_amount': invested_amount,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            'annualized_return': annualized_return,
            'days_held': days_held
        }

    def compare_with_sp500(self, position):
        if not position.purchased_at:
            return {'sp500_return': Decimal('0'), 'alpha': Decimal('0')}

        sp500_return = self.external_apis.get_sp500_performance(
            position.purchased_at.date(),
            timezone.now().date()
        )

        performance = self.calculate_position_performance(position)
        alpha = performance['profit_loss_percentage'] - sp500_return

        return {
            'sp500_return': sp500_return,
            'alpha': alpha
        }

    def compare_with_inflation(self, position):
        if not position.purchased_at:
            return {'inflation': Decimal('0'), 'real_return': Decimal('0')}

        inflation = self.external_apis.get_indec_inflation(
            position.purchased_at.date(),
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

        for position in positions:
            current_price = self.external_apis.get_current_price(position.stock.ticker) or position.stock_price_local
            total_invested += position.amount * position.stock_price_local
            total_current_value += position.amount * current_price

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

        sector_distribution = {}
        for position in positions:
            sector = position.stock.sector.name if position.stock.sector else 'Sin sector'
            if sector not in sector_distribution:
                sector_distribution[sector] = Decimal('0')
            sector_distribution[sector] += position.amount * position.stock_price_local

        return {
            'total_invested': total_invested,
            'total_current_value': total_current_value,
            'profit_loss': profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            'position_count': len(positions),
            'sp500_return': total_sp500_return,
            'alpha': alpha,
            'inflation': total_inflation,
            'real_return': real_return,
            'sector_distribution': sector_distribution
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
            price = Decimal(str(position.stock_price_local))
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

    def get_totals(self, user_id):
        positions = get_cash_positions_by_user(user_id)
        total_ars = sum(c.amount for c in positions if c.currency == 'ARS')
        total_usd = sum(c.amount for c in positions if c.currency == 'USD')
        try:
            ccl = Decimal(str(get_ccl_rate()))
            total_ars_equivalent = total_ars + total_usd * ccl
        except Exception:
            ccl = Decimal('0')
            total_ars_equivalent = total_ars
        return {
            'total_ars': total_ars,
            'total_usd': total_usd,
            'ccl': ccl,
            'total_ars_equivalent': total_ars_equivalent,
        }


class OrderManager:
    def get_position_orders(self, position_id):
        return get_orders_by_position(position_id)

    def get_order(self, order_id, user_id=None):
        return get_order_by_id(order_id, user_id)

    def add_order(self, position_id, amount, fulfill_datetime, total_fees, price_local, price_usd):
        if amount <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if price_local <= 0 or price_usd <= 0:
            raise ValueError("El precio debe ser mayor a 0")

        return create_order(position_id, amount, fulfill_datetime, total_fees, price_local, price_usd)

    def remove_order(self, order_id):
        delete_order(order_id)
