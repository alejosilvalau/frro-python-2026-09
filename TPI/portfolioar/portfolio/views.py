from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .business import PortfolioManager, OrderManager, CashManager
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
    return render(request, 'portfolio/position_list.html', {'page': page})


@login_required
def position_detail(request, position_id):
    portfolio_manager = PortfolioManager()
    position = portfolio_manager.get_position(position_id, request.user.id)
    performance = portfolio_manager.calculate_position_performance(position)
    sp500_comparison = portfolio_manager.compare_with_sp500(position)
    inflation_comparison = portfolio_manager.compare_with_inflation(position)
    technical_indicators = portfolio_manager.get_technical_indicators(position)

    order_manager = OrderManager()
    orders = order_manager.get_position_orders(position_id)

    return render(request, 'portfolio/position_detail.html', {
        'position': position,
        'performance': performance,
        'sp500': sp500_comparison,
        'inflation': inflation_comparison,
        'indicators': technical_indicators,
        'orders': orders
    })


@login_required
def position_create(request):
    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        broker_id = request.POST.get('broker_id')
        amount = int(request.POST.get('amount', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))
        purchased_at = request.POST.get('purchased_at')

        try:
            portfolio_manager = PortfolioManager()
            portfolio_manager.add_position(
                request.user.id, stock_id, broker_id, amount, price_local, price_usd, purchased_at
            )
            return redirect('portfolio:position_list')
        except ValueError as e:
            stocks = StockManager().get_all()
            brokers = BrokerManager().get_all()
            return render(request, 'portfolio/position_form.html', {
                'error': str(e),
                'stocks': stocks,
                'brokers': brokers
            })

    stocks = StockManager().get_all()
    brokers = BrokerManager().get_all()
    return render(request, 'portfolio/position_form.html', {
        'stocks': stocks,
        'brokers': brokers
    })


@login_required
def position_update(request, position_id):
    portfolio_manager = PortfolioManager()
    position = portfolio_manager.get_position(position_id, request.user.id)
    stocks = StockManager().get_all()
    brokers = BrokerManager().get_all()

    if request.method == 'POST':
        amount = int(request.POST.get('amount', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))

        try:
            portfolio_manager.update_position(position_id, amount, price_local, price_usd)
            return redirect('portfolio:position_detail', position_id=position_id)
        except ValueError as e:
            return render(request, 'portfolio/position_form.html', {
                'position': position,
                'stocks': stocks,
                'brokers': brokers,
                'error': str(e)
            })

    return render(request, 'portfolio/position_form.html', {
        'position': position,
        'stocks': stocks,
        'brokers': brokers,
    })


@login_required
def position_delete(request, position_id):
    portfolio_manager = PortfolioManager()
    portfolio_manager.get_position(position_id, request.user.id)
    portfolio_manager.remove_position(position_id)
    return redirect('portfolio:position_list')


@login_required
def order_create(request, position_id):
    portfolio_manager = PortfolioManager()
    portfolio_manager.get_position(position_id, request.user.id)

    if request.method == 'POST':
        amount = int(request.POST.get('amount', 0))
        fulfill_datetime = request.POST.get('fulfill_datetime')
        total_fees = float(request.POST.get('total_fees', 0))
        price_local = float(request.POST.get('price_local', 0))
        price_usd = float(request.POST.get('price_usd', 0))

        try:
            order_manager = OrderManager()
            order_manager.add_order(position_id, amount, fulfill_datetime, total_fees, price_local, price_usd)
            return redirect('portfolio:position_detail', position_id=position_id)
        except ValueError as e:
            return render(request, 'portfolio/order_form.html', {
                'position_id': position_id,
                'error': str(e)
            })

    return render(request, 'portfolio/order_form.html', {'position_id': position_id})


@login_required
def order_delete(request, order_id):
    order_manager = OrderManager()
    order_manager.get_order(order_id, request.user.id)
    order_manager.remove_order(order_id)
    return redirect('portfolio:position_list')


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
