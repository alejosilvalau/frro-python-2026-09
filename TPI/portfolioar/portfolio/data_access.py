import os
import time

import requests
from django.shortcuts import get_object_or_404

from .models import Position, Order
from core.data_access import get_user_by_id, get_stock_by_id, get_broker_by_id

_IOL_BASE = 'https://api.invertironline.com'
_iol_token = {'access_token': None, 'refresh_token': None, 'expires_at': 0}


def _iol_authenticate():
    resp = requests.post(
        f'{_IOL_BASE}/token',
        data={
            'grant_type': 'password',
            'username': os.environ.get('IOL_USER', ''),
            'password': os.environ.get('IOL_PASSWORD', ''),
            'scope': 'APIv2',
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _iol_token['access_token'] = data['access_token']
    _iol_token['refresh_token'] = data['refresh_token']
    _iol_token['expires_at'] = time.time() + data.get('expires_in', 1800) - 60
    return _iol_token['access_token']


def _iol_refresh():
    resp = requests.post(
        f'{_IOL_BASE}/token',
        data={
            'grant_type': 'refresh_token',
            'refresh_token': _iol_token['refresh_token'],
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _iol_token['access_token'] = data['access_token']
    _iol_token['refresh_token'] = data.get('refresh_token', _iol_token['refresh_token'])
    _iol_token['expires_at'] = time.time() + data.get('expires_in', 1800) - 60
    return _iol_token['access_token']


def _get_iol_token():
    if _iol_token['access_token'] and time.time() < _iol_token['expires_at']:
        return _iol_token['access_token']
    if _iol_token['refresh_token']:
        try:
            return _iol_refresh()
        except Exception:
            pass
    return _iol_authenticate()


def get_stock_price_from_iol(ticker, mercado='bCBA'):
    token = _get_iol_token()
    url = f'{_IOL_BASE}/api/v2/{mercado}/Titulos/{ticker}/Cotizacion'
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    resp.raise_for_status()
    return resp.json().get('ultimoPrecio')


def get_sp500_return(start_date, end_date):
    import yfinance as yf
    hist = yf.Ticker('^GSPC').history(
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        auto_adjust=True,
    )
    if len(hist) >= 2:
        return float(hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
    return None


def get_historical_prices(ticker, period='6mo'):
    import yfinance as yf
    return yf.Ticker(ticker).history(period=period, auto_adjust=True)


def get_positions_by_user(user_id):
    return Position.objects.filter(user_id=user_id)


def get_position_by_id(position_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Position, id=position_id, user_id=user_id)
    return get_object_or_404(Position, id=position_id)


def create_position(user_id, stock_id, broker_id, amount, stock_price_local, stock_price_usd, purchased_at):
    user = get_user_by_id(user_id)
    stock = get_stock_by_id(stock_id)
    broker = get_broker_by_id(broker_id)

    position = Position(
        user=user,
        stock=stock,
        broker=broker,
        amount=amount,
        stock_price_local=stock_price_local,
        stock_price_usd=stock_price_usd,
        purchased_at=purchased_at
    )
    position.save()
    return position


def update_position(position_id, amount=None, stock_price_local=None, stock_price_usd=None):
    position = Position.objects.get(id=position_id)
    if amount is not None:
        position.amount = amount
    if stock_price_local is not None:
        position.stock_price_local = stock_price_local
    if stock_price_usd is not None:
        position.stock_price_usd = stock_price_usd
    position.save()
    return position


def delete_position(position_id):
    Position.objects.filter(id=position_id).delete()


def get_orders_by_position(position_id):
    return Order.objects.filter(position_id=position_id)


def create_order(position_id, amount, fulfill_datetime, total_fees, price_local, price_usd):
    position = Position.objects.get(id=position_id)

    order = Order(
        position=position,
        amount=amount,
        fulfill_datetime=fulfill_datetime,
        total_fees=total_fees,
        price_local=price_local,
        price_usd=price_usd
    )
    order.save()
    return order


def get_order_by_id(order_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Order, id=order_id, position__user_id=user_id)
    return get_object_or_404(Order, id=order_id)


def delete_order(order_id):
    Order.objects.filter(id=order_id).delete()
