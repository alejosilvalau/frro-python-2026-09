import math
import os
import time
from datetime import timedelta

import requests
from django.core.cache import cache
from django.shortcuts import get_object_or_404

from .models import Position, Lot, Sale, SaleLot, CashPosition, CashTransaction
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
    quote = get_iol_quote(ticker, mercado)
    return quote.get('ultimoPrecio')


def get_iol_quote(ticker, mercado='bCBA'):
    token = _get_iol_token()
    url = f'{_IOL_BASE}/api/v2/{mercado}/Titulos/{ticker}/Cotizacion'
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_iol_daily_series(ticker, start_date, end_date_exclusive, mercado='bCBA'):
    cache_key = f'iol:daily:{mercado}:{ticker}:{start_date.isoformat()}:{end_date_exclusive.isoformat()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    token = _get_iol_token()
    url = (
        f'{_IOL_BASE}/api/v2/{mercado}/Titulos/{ticker}/Cotizacion/seriehistorica/'
        f'{start_date.isoformat()}/{end_date_exclusive.isoformat()}/sinAjustar'
    )
    response = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    response.raise_for_status()
    data = response.json()
    cache.set(cache_key, data, timeout=24 * 60 * 60)
    return data


def get_historical_ccl(day):
    cache_key = f'argentinadatos:ccl:{day.isoformat()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    response = requests.get(
        f'https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui/{day:%Y/%m/%d}',
        timeout=8,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    cache.set(cache_key, data, timeout=24 * 60 * 60)
    return data


def get_holidays(year):
    cache_key = f'argentinadatos:holidays:{year}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    response = requests.get(f'https://api.argentinadatos.com/v1/feriados/{year}', timeout=8)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    cache.set(cache_key, data, timeout=7 * 24 * 60 * 60)
    return data


def get_ccl_rate():
    resp = requests.get('https://dolarapi.com/v1/dolares/contadoconliqui', timeout=8)
    resp.raise_for_status()
    return float(resp.json()['venta'])


def get_indec_inflation_series(start_date, end_date):
    response = requests.get(
        'https://apis.datos.gob.ar/series/api/series/',
        params={
            'ids': '148.3_INIVELNAL_DICI_M_26',
            'start_date': start_date.strftime('%Y-%m'),
            'end_date': end_date.strftime('%Y-%m'),
            'format': 'json',
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get('data', [])


def get_sp500_return(start_date, end_date):
    import yfinance as yf
    hist = yf.Ticker('^GSPC').history(
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d'),
        auto_adjust=True,
    )
    if len(hist) >= 2:
        start_close = hist['Close'].iloc[0]
        end_close = hist['Close'].iloc[-1]
        if not (math.isfinite(start_close) and math.isfinite(end_close)) or start_close == 0:
            return None
        return float(end_close / start_close - 1) * 100
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


def get_position_for_update(position_id):
    return Position.objects.select_for_update().get(id=position_id)


def create_position(user_id, stock_id, broker_id, opened_at, status='open'):
    user = get_user_by_id(user_id)
    stock = get_stock_by_id(stock_id)
    broker = get_broker_by_id(broker_id)

    position = Position(
        user=user,
        stock=stock,
        broker=broker,
        opened_at=opened_at,
        status=status,
    )
    position.save()
    return position


def update_position_status(position_id, status):
    Position.objects.filter(id=position_id).update(status=status)


def delete_position(position_id):
    Position.objects.filter(id=position_id).delete()


def get_lots_by_position(position_id):
    return Lot.objects.filter(position_id=position_id).order_by('purchased_at', 'id')


def get_lots_by_position_for_update(position_id):
    return Lot.objects.select_for_update().filter(position_id=position_id).order_by('purchased_at', 'id')


def get_lot_by_id(lot_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Lot, id=lot_id, position__user_id=user_id)
    return get_object_or_404(Lot, id=lot_id)


def get_lot_for_update(lot_id):
    return Lot.objects.select_for_update().get(id=lot_id)


def create_lot(
    position_id, amount, price_local, price_usd, purchased_at, purchase_currency='ARS', fees=0,
    pricing_snapshot=None,
):
    position = Position.objects.get(id=position_id)

    snapshot_fields = {}
    if pricing_snapshot is not None:
        snapshot_fields = {
            'price_input_currency': pricing_snapshot.price_input_currency,
            'price_origin': pricing_snapshot.price_origin,
            'price_source': pricing_snapshot.price_source,
            'price_quote_date': pricing_snapshot.price_quote_date,
            'quote_currency': pricing_snapshot.quote_currency,
            'quote_unit': pricing_snapshot.quote_unit,
            'ccl_rate': pricing_snapshot.ccl_rate,
            'ccl_date': pricing_snapshot.ccl_date,
            'ccl_source': pricing_snapshot.ccl_source,
        }
    lot = Lot(
        position=position,
        amount=amount,
        price_local=price_local,
        price_usd=price_usd,
        purchased_at=purchased_at,
        purchase_currency=purchase_currency,
        fees=fees,
        **snapshot_fields,
    )
    lot.save()
    return lot


def delete_lot(lot_id):
    Lot.objects.filter(id=lot_id).delete()


def get_sale_lots_for_lots(lot_ids):
    return SaleLot.objects.filter(lot_id__in=lot_ids)


def get_sale_lots_by_position(position_id):
    return SaleLot.objects.filter(sale__position_id=position_id).select_related('lot', 'sale')


def create_sale(
    position_id, amount, price_local, price_usd, sold_at, sell_currency, realized_pnl_ars,
    realized_pnl_usd, pricing_snapshot=None,
):
    position = Position.objects.get(id=position_id)

    snapshot_fields = {}
    if pricing_snapshot is not None:
        snapshot_fields = {
            'price_input_currency': pricing_snapshot.price_input_currency,
            'price_origin': pricing_snapshot.price_origin,
            'price_source': pricing_snapshot.price_source,
            'price_quote_date': pricing_snapshot.price_quote_date,
            'quote_currency': pricing_snapshot.quote_currency,
            'quote_unit': pricing_snapshot.quote_unit,
            'ccl_rate': pricing_snapshot.ccl_rate,
            'ccl_date': pricing_snapshot.ccl_date,
            'ccl_source': pricing_snapshot.ccl_source,
        }
    sale = Sale(
        position=position,
        amount=amount,
        price_local=price_local,
        price_usd=price_usd,
        sold_at=sold_at,
        sell_currency=sell_currency,
        realized_pnl_ars=realized_pnl_ars,
        realized_pnl_usd=realized_pnl_usd,
        **snapshot_fields,
    )
    sale.save()
    return sale


def create_sale_lot(sale_id, lot_id, amount_consumed, cost_price_local, cost_price_usd):
    sale_lot = SaleLot(
        sale_id=sale_id,
        lot_id=lot_id,
        amount_consumed=amount_consumed,
        cost_price_local=cost_price_local,
        cost_price_usd=cost_price_usd,
    )
    sale_lot.save()
    return sale_lot


def get_sales_by_position(position_id):
    return Sale.objects.filter(position_id=position_id)


def get_sale_by_id(sale_id, user_id=None):
    if user_id is not None:
        return get_object_or_404(Sale, id=sale_id, position__user_id=user_id)
    return get_object_or_404(Sale, id=sale_id)


def get_cash_positions_by_user(user_id):
    return CashPosition.objects.filter(user_id=user_id)


def get_cash_positions_by_user_for_update(user_id):
    return CashPosition.objects.select_for_update().filter(user_id=user_id)


def get_cash_position_by_id(cash_id, user_id=None):
    from django.shortcuts import get_object_or_404
    if user_id is not None:
        return get_object_or_404(CashPosition, id=cash_id, user_id=user_id)
    return get_object_or_404(CashPosition, id=cash_id)


def create_cash_position(user_id, currency, amount, description):
    from core.data_access import get_user_by_id
    user = get_user_by_id(user_id)
    cash = CashPosition(user=user, currency=currency, amount=amount, description=description)
    cash.save()
    return cash


def update_cash_position(cash_id, amount, description):
    cash = CashPosition.objects.get(id=cash_id)
    cash.amount = amount
    cash.description = description
    cash.save()
    return cash


def delete_cash_position(cash_id):
    CashPosition.objects.filter(id=cash_id).delete()


def get_cash_transactions_by_user(user_id):
    return CashTransaction.objects.filter(user_id=user_id)


def get_cash_transactions_by_position(position_id, tipo=None):
    qs = CashTransaction.objects.filter(position_id=position_id)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return qs


def get_cash_transaction_by_lot(lot_id, tipo=None):
    qs = CashTransaction.objects.filter(lot_id=lot_id)
    if tipo:
        qs = qs.filter(tipo=tipo)
    return qs.first()


def create_cash_transaction(user_id, currency, amount, tipo, position_id=None, lot_id=None, sale_id=None):
    from core.data_access import get_user_by_id as _get_user
    user = _get_user(user_id)
    position = Position.objects.get(id=position_id) if position_id else None
    lot = Lot.objects.get(id=lot_id) if lot_id else None
    sale = Sale.objects.get(id=sale_id) if sale_id else None
    tx = CashTransaction(user=user, currency=currency, amount=amount, tipo=tipo, position=position, lot=lot, sale=sale)
    tx.save()
    return tx
