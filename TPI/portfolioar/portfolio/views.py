from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .business import PortfolioManager, LotManager, SaleManager, CashManager
from .data_access import get_stock_price_from_iol, get_ccl_rate
from core.business import StockManager, BrokerManager
from core.data_access import get_stock_by_id


@login_required
def dashboard(request):
    portfolio_manager = PortfolioManager()
    cash_manager = CashManager()
    summary = portfolio_manager.calculate_portfolio_summary(request.user.id)
    cash_totals = cash_manager.get_totals(request.user.id)
    positions = portfolio_manager.get_user_positions(request.user.id)

    positions_with_performance = []
    for position in positions:
        performance = portfolio_manager.calculate_position_performance(position)
        sp500_comparison = portfolio_manager.compare_with_sp500(position)
        inflation_comparison = portfolio_manager.compare_with_inflation(position)
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
    sp500_comparison = portfolio_manager.compare_with_sp500(position)
    inflation_comparison = portfolio_manager.compare_with_inflation(position)
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
        amount = int(request.POST.get('amount', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))
        purchased_at = request.POST.get('purchased_at')
        purchase_currency = request.POST.get('purchase_currency', 'ARS')

        try:
            portfolio_manager = PortfolioManager()
            portfolio_manager.add_position(
                request.user.id, stock_id, broker_id, amount, price_local, price_usd, purchased_at, purchase_currency
            )
            return redirect('portfolio:position_list')
        except ValueError as e:
            stocks = StockManager().get_all()
            brokers = BrokerManager().get_all()
            return render(request, 'portfolio/position_form.html', {
                'error': str(e),
                'stocks': stocks,
                'brokers': brokers,
                'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
                'available_usd': cash_manager.get_available(request.user.id, 'USD'),
            })

    stocks = StockManager().get_all()
    brokers = BrokerManager().get_all()
    return render(request, 'portfolio/position_form.html', {
        'stocks': stocks,
        'brokers': brokers,
        'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
        'available_usd': cash_manager.get_available(request.user.id, 'USD'),
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
        amount = int(request.POST.get('amount', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))
        purchased_at = request.POST.get('purchased_at')
        purchase_currency = request.POST.get('purchase_currency', 'ARS')
        fees = float(request.POST.get('fees', 0) or 0)

        try:
            lot_manager = LotManager()
            lot_manager.add_lot(position_id, amount, price_local, price_usd, purchased_at, purchase_currency, fees)
            return redirect('portfolio:position_detail', position_id=position_id)
        except ValueError as e:
            return render(request, 'portfolio/lot_form.html', {
                'position': position,
                'error': str(e),
                'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
                'available_usd': cash_manager.get_available(request.user.id, 'USD'),
            })

    return render(request, 'portfolio/lot_form.html', {
        'position': position,
        'available_ars': cash_manager.get_available(request.user.id, 'ARS'),
        'available_usd': cash_manager.get_available(request.user.id, 'USD'),
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
        amount = int(request.POST.get('amount', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))
        sold_at = request.POST.get('sold_at')
        sell_currency = request.POST.get('sell_currency', 'ARS')

        try:
            sale_manager = SaleManager()
            sale_manager.add_sale(position_id, amount, price_local, price_usd, sold_at, sell_currency)
            return redirect('portfolio:position_detail', position_id=position_id)
        except ValueError as e:
            return render(request, 'portfolio/sale_form.html', {
                'position': position,
                'open_summary': open_summary,
                'error': str(e),
            })

    return render(request, 'portfolio/sale_form.html', {
        'position': position,
        'open_summary': open_summary,
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
    if not stock_id:
        return JsonResponse({'error': 'stock_id requerido'}, status=400)
    try:
        stock = get_stock_by_id(stock_id)
        price_ars = get_stock_price_from_iol(stock.ticker)
        ccl = get_ccl_rate()
        price_usd = round(price_ars / ccl, 4) if ccl else None
        return JsonResponse({
            'ticker': stock.ticker,
            'price_ars': price_ars,
            'price_usd': price_usd,
            'ccl': ccl,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)
