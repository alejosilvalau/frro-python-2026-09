from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .business import (
    PortfolioManager, LotManager, SaleManager, CashManager, MarketDataManager,
    is_business_day, last_business_day, default_operation_datetime,
)
from core.business import StockManager, BrokerManager


def _parse_integer(value, field_name):
    number = Decimal(value)
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"{field_name} debe ser un número entero válido")
    return int(number)


def _parse_decimal(value, field_name):
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError(f"{field_name} debe ser un número válido")
    return number


def _parse_operation_datetime(value, field_name):
    parsed = parse_datetime(value or '')
    if parsed is None:
        raise ValueError(f"La fecha de {field_name} es inválida")
    if settings.USE_TZ and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    elif not settings.USE_TZ and timezone.is_aware(parsed):
        parsed = timezone.make_naive(parsed, timezone.get_current_timezone())
    if parsed > timezone.now():
        raise ValueError(f"La fecha de {field_name} no puede estar en el futuro")
    return parsed


@login_required
def dashboard(request):
    portfolio_manager = PortfolioManager()
    cash_manager = CashManager()
    cash_totals = cash_manager.get_totals(request.user.id)
    summary = portfolio_manager.calculate_portfolio_summary(request.user.id, cash_totals=cash_totals)
    positions = portfolio_manager.get_user_positions(request.user.id)

    positions_with_performance = []
    for position in positions:
        performance = portfolio_manager.calculate_position_performance(position)
        sp500_comparison = portfolio_manager.compare_with_sp500(position, performance)
        inflation_comparison = portfolio_manager.compare_with_inflation(position, performance)
        technical_indicators = portfolio_manager.get_technical_indicators(position)

        positions_with_performance.append({
            'position': position,
            'performance': performance,
            'sp500': sp500_comparison,
            'inflation': inflation_comparison,
            'indicators': technical_indicators
        })

    return render(request, 'portfolio/dashboard.html', {
        'summary': summary,
        'cash_totals': cash_totals,
        'positions': positions,
        'positions_with_performance': positions_with_performance,
    })


@login_required
def position_list(request):
    portfolio_manager = PortfolioManager()
    positions = portfolio_manager.get_user_positions(request.user.id)
    paginator = Paginator(positions, 10)
    page = paginator.get_page(request.GET.get('page'))

    items = [
        {'position': p, 'summary': portfolio_manager.get_open_position_summary(p)}
        for p in page
    ]
    return render(request, 'portfolio/position_list.html', {'page': page, 'items': items})


@login_required
def position_detail(request, position_id):
    portfolio_manager = PortfolioManager()
    position = portfolio_manager.get_position(position_id, request.user.id)
    performance = portfolio_manager.calculate_position_performance(position)
    sp500_comparison = portfolio_manager.compare_with_sp500(position, performance)
    inflation_comparison = portfolio_manager.compare_with_inflation(position, performance)
    technical_indicators = portfolio_manager.get_technical_indicators(position)
    lots_with_remaining = portfolio_manager.get_lots_with_remaining(position_id)

    sale_manager = SaleManager()
    sales = sale_manager.get_position_sales(position_id)

    return render(request, 'portfolio/position_detail.html', {
        'position': position,
        'performance': performance,
        'sp500': sp500_comparison,
        'inflation': inflation_comparison,
        'indicators': technical_indicators,
        'lots_with_remaining': lots_with_remaining,
        'sales': sales,
    })


@login_required
def position_create(request):
    cash_manager = CashManager()
    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        broker_id = request.POST.get('broker_id')

        try:
            amount = _parse_integer(request.POST.get('amount'), 'La cantidad')
            price = _parse_decimal(request.POST.get('price'), 'El precio')
            purchased_at = _parse_operation_datetime(request.POST.get('purchased_at'), 'compra')
            purchase_currency = request.POST.get('purchase_currency', 'ARS')
            portfolio_manager = PortfolioManager()
            portfolio_manager.add_position(
                request.user.id, stock_id, broker_id, amount, price, purchased_at, purchase_currency,
                price_input_currency=request.POST.get('price_input_currency', purchase_currency),
                client_ccl_rate=request.POST.get('client_ccl_rate'),
                manual_ccl_rate=request.POST.get('manual_ccl_rate'),
            )
            return redirect('portfolio:position_list')
        except (ValueError, InvalidOperation, TypeError) as e:
            stock_manager = StockManager()
            stocks = stock_manager.get_all()
            brokers = BrokerManager().get_all()
            return render(request, 'portfolio/position_form.html', {
                'error': str(e),
                'stocks': stocks,
                'stock_types': stock_manager.get_type_choices(),
                'brokers': brokers,
                'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
                'available_usd': cash_manager.get_available(request.user.id, 'USD'),
                'default_operation_datetime': default_operation_datetime(),
            })

    stock_manager = StockManager()
    stocks = stock_manager.get_all()
    brokers = BrokerManager().get_all()
    return render(request, 'portfolio/position_form.html', {
        'stocks': stocks,
        'stock_types': stock_manager.get_type_choices(),
        'brokers': brokers,
        'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
        'available_usd': cash_manager.get_available(request.user.id, 'USD'),
        'default_operation_datetime': default_operation_datetime(),
    })


@login_required
def position_delete(request, position_id):
    portfolio_manager = PortfolioManager()
    portfolio_manager.get_position(position_id, request.user.id)
    try:
        portfolio_manager.remove_position(position_id)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('portfolio:position_detail', position_id=position_id)
    return redirect('portfolio:position_list')


@login_required
def lot_create(request, position_id):
    portfolio_manager = PortfolioManager()
    position = portfolio_manager.get_position(position_id, request.user.id)
    cash_manager = CashManager()

    if request.method == 'POST':
        try:
            amount = _parse_integer(request.POST.get('amount'), 'La cantidad')
            price = _parse_decimal(request.POST.get('price'), 'El precio')
            purchased_at = _parse_operation_datetime(request.POST.get('purchased_at'), 'compra')
            purchase_currency = request.POST.get('purchase_currency', 'ARS')
            fees = _parse_decimal(request.POST.get('fees', '0') or '0', 'La comisión')
            lot_manager = LotManager()
            lot_manager.add_lot(
                position_id, amount, price, purchased_at, purchase_currency, fees,
                price_input_currency=request.POST.get('price_input_currency', purchase_currency),
                client_ccl_rate=request.POST.get('client_ccl_rate'),
                manual_ccl_rate=request.POST.get('manual_ccl_rate'),
            )
            return redirect('portfolio:position_detail', position_id=position_id)
        except (ValueError, InvalidOperation, TypeError) as e:
            return render(request, 'portfolio/lot_form.html', {
                'position': position,
                'error': str(e),
                'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
                'available_usd': cash_manager.get_available(request.user.id, 'USD'),
                'default_operation_datetime': default_operation_datetime(),
            })

    return render(request, 'portfolio/lot_form.html', {
        'position': position,
        'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
        'available_usd': cash_manager.get_available(request.user.id, 'USD'),
        'default_operation_datetime': default_operation_datetime(),
    })


@login_required
def lot_delete(request, lot_id):
    lot_manager = LotManager()
    lot = lot_manager.get_lot(lot_id, request.user.id)
    position_id = lot.position_id
    try:
        lot_manager.remove_lot(lot_id)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('portfolio:position_detail', position_id=position_id)


@login_required
def sale_create(request, position_id):
    portfolio_manager = PortfolioManager()
    position = portfolio_manager.get_position(position_id, request.user.id)
    open_summary = portfolio_manager.get_open_position_summary(position)

    if request.method == 'POST':
        try:
            amount = _parse_integer(request.POST.get('amount'), 'La cantidad')
            price = _parse_decimal(request.POST.get('price'), 'El precio')
            sold_at = _parse_operation_datetime(request.POST.get('sold_at'), 'venta')
            sell_currency = request.POST.get('sell_currency', 'ARS')
            sale_manager = SaleManager()
            sale_manager.add_sale(
                position_id, amount, price, sold_at, sell_currency,
                price_input_currency=request.POST.get('price_input_currency', sell_currency),
                client_ccl_rate=request.POST.get('client_ccl_rate'),
                manual_ccl_rate=request.POST.get('manual_ccl_rate'),
            )
            return redirect('portfolio:position_detail', position_id=position_id)
        except (ValueError, InvalidOperation, TypeError) as e:
            return render(request, 'portfolio/sale_form.html', {
                'position': position,
                'open_summary': open_summary,
                'error': str(e),
                'default_operation_datetime': default_operation_datetime(),
            })

    return render(request, 'portfolio/sale_form.html', {
        'position': position,
        'open_summary': open_summary,
        'default_operation_datetime': default_operation_datetime(),
    })


@login_required
def cash_list(request):
    cash_manager = CashManager()
    cash_positions = cash_manager.get_user_cash(request.user.id)
    totals = cash_manager.get_totals(request.user.id)
    return render(request, 'portfolio/cash_list.html', {
        'cash_positions': cash_positions,
        'totals': totals,
    })


@login_required
def cash_create(request):
    if request.method == 'POST':
        currency = request.POST.get('currency')
        description = request.POST.get('description', '')
        try:
            amount = float(request.POST.get('amount', 0))
            cash_manager = CashManager()
            cash_manager.add_cash(request.user.id, currency, amount, description)
            return redirect('portfolio:cash_list')
        except ValueError as e:
            return render(request, 'portfolio/cash_form.html', {'error': str(e)})
    return render(request, 'portfolio/cash_form.html')


@login_required
def cash_update(request, cash_id):
    cash_manager = CashManager()
    cash = cash_manager.get_cash(cash_id, request.user.id)
    if request.method == 'POST':
        description = request.POST.get('description', '')
        try:
            amount = float(request.POST.get('amount', 0))
            cash_manager.update_cash(cash_id, amount, description)
            return redirect('portfolio:cash_list')
        except ValueError as e:
            return render(request, 'portfolio/cash_form.html', {'cash': cash, 'error': str(e)})
    return render(request, 'portfolio/cash_form.html', {'cash': cash})


@login_required
def cash_delete(request, cash_id):
    cash_manager = CashManager()
    cash_manager.get_cash(cash_id, request.user.id)
    cash_manager.remove_cash(cash_id)
    return redirect('portfolio:cash_list')


@login_required
def api_instrument_price(request):
    stock_id = request.GET.get('stock_id')
    raw_date = request.GET.get('fecha')
    try:
        if raw_date:
            day = datetime.strptime(raw_date, '%Y-%m-%d').date()
        else:
            today = timezone.localdate() if settings.USE_TZ else timezone.now().date()
            day = last_business_day(today)
        today = timezone.localdate() if settings.USE_TZ else timezone.now().date()
        if day > today:
            return JsonResponse({'error': 'fecha_futura'}, status=400)
        if not is_business_day(day):
            return JsonResponse({
                'error': 'dia_no_habil',
                'last_business_day': last_business_day(day).isoformat(),
            }, status=400)

        manager = MarketDataManager()
        ccl, ccl_error = manager.get_ccl_for_date(day)
        quote = quote_error = None
        quote_unit = 1
        ticker = None
        if stock_id:
            stock = StockManager().get_by_id(stock_id)
            ticker = stock.ticker
            quote, quote_error = manager.get_quote_for_date(stock, day)
            quote_unit = StockManager().get_quote_unit(stock)

        prices = {'ARS': None, 'USD': None}
        if quote and ccl:
            if quote.currency == 'ARS':
                prices['ARS'] = quote.price
                prices['USD'] = (quote.price / ccl.rate).quantize(Decimal('0.0001'))
            else:
                prices['USD'] = quote.price
                prices['ARS'] = (quote.price * ccl.rate).quantize(Decimal('0.0001'))
        return JsonResponse({
            'ticker': ticker,
            'date': day.isoformat(),
            'quote': None if quote is None else {
                'price': str(quote.price), 'currency': quote.currency,
                'quote_date': quote.quote_date.isoformat(), 'source': quote.source,
                'observed_at': quote.observed_at,
            },
            'quote_error': quote_error,
            'ccl': None if ccl is None else {
                'rate': str(ccl.rate), 'ccl_date': ccl.ccl_date.isoformat(),
                'source': ccl.source, 'side': ccl.side,
            },
            'ccl_error': ccl_error,
            'prices': {currency: str(value) if value is not None else None for currency, value in prices.items()},
            'quote_unit': quote_unit,
            # Compatibilidad temporal con el autocompletado previo.
            'price_ars': float(prices['ARS']) if prices['ARS'] is not None else None,
            'price_usd': float(prices['USD']) if prices['USD'] is not None else None,
            'ccl_rate': float(ccl.rate) if ccl else None,
        })
    except ValueError:
        return JsonResponse({'error': 'fecha_invalida'}, status=400)
    except Exception as error:
        return JsonResponse({'error': str(error)}, status=502)
