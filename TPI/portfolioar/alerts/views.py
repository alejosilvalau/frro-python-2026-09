from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .business import AlertManager, IndicatorManager, ConditionManager
from .models import AlertCondition
from core.business import StockManager


@login_required
def alert_list(request):
    alert_manager = AlertManager()
    alerts = alert_manager.get_user_alerts(request.user.id)

    return render(request, 'alerts/alert_list.html', {'alerts': alerts})


@login_required
def alert_detail(request, alert_id):
    alert_manager = AlertManager()
    alert = alert_manager.get_alert(alert_id, request.user.id)
    conditions = ConditionManager().get_all()
    assigned_conditions = alert_manager.get_alert_conditions(alert)
    triggers = alert_manager.get_alert_triggers(alert_id)

    return render(request, 'alerts/alert_detail.html', {
        'alert': alert,
        'conditions': conditions,
        'assigned_conditions': assigned_conditions,
        'triggers': triggers,
    })


@login_required
def alert_create(request):
    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        name = request.POST.get('name')
        is_active = request.POST.get('is_active') == 'on'

        try:
            alert_manager = AlertManager()
            alert_manager.create_alert(request.user.id, stock_id, name, is_active)
            return redirect('alerts:alert_list')
        except ValueError as e:
            stocks = StockManager().get_all()
            return render(request, 'alerts/alert_form.html', {
                'error': str(e),
                'stocks': stocks,
            })

    stocks = StockManager().get_all()
    return render(request, 'alerts/alert_form.html', {'stocks': stocks})


@login_required
def alert_update(request, alert_id):
    alert_manager = AlertManager()
    alert = alert_manager.get_alert(alert_id, request.user.id)

    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        name = request.POST.get('name')
        is_active = request.POST.get('is_active') == 'on'

        try:
            alert_manager.update_alert(alert_id, name, is_active, stock_id)
            return redirect('alerts:alert_detail', alert_id=alert_id)
        except ValueError as e:
            stocks = StockManager().get_all()
            return render(request, 'alerts/alert_form.html', {
                'alert': alert,
                'stocks': stocks,
                'error': str(e)
            })

    stocks = StockManager().get_all()
    return render(request, 'alerts/alert_form.html', {'alert': alert, 'stocks': stocks})


@login_required
@require_POST
def alert_delete(request, alert_id):
    alert_manager = AlertManager()
    alert_manager.get_alert(alert_id, request.user.id)
    alert_manager.delete_alert(alert_id)
    return redirect('alerts:alert_list')


@login_required
def alert_add_condition(request, alert_id):
    if request.method == 'POST':
        condition_id = request.POST.get('condition_id')

        alert_manager = AlertManager()
        alert_manager.get_alert(alert_id, request.user.id)
        alert_manager.add_condition(alert_id, condition_id)
        return redirect('alerts:alert_detail', alert_id=alert_id)

    return redirect('alerts:alert_detail', alert_id=alert_id)


@login_required
@require_POST
def alert_remove_condition(request, alert_id, condition_id):
    alert_manager = AlertManager()
    alert_manager.get_alert(alert_id, request.user.id)
    alert_manager.remove_condition(alert_id, condition_id)
    return redirect('alerts:alert_detail', alert_id=alert_id)


@login_required
def indicator_list(request):
    indicators = IndicatorManager().get_all()

    return render(request, 'alerts/indicator_list.html', {'indicators': indicators})


@login_required
def condition_list(request):
    conditions = ConditionManager().get_all()

    return render(request, 'alerts/condition_list.html', {'conditions': conditions})


@login_required
def condition_create(request):
    indicators = IndicatorManager().get_all()
    if request.method == 'POST':
        try:
            indicator_id = request.POST.get('indicator_id')
            operator = request.POST.get('operator')
            threshold_value = Decimal(request.POST.get('threshold_value'))
            ConditionManager().create(indicator_id, operator, threshold_value)
            return redirect('alerts:condition_list')
        except (ValueError, InvalidOperation, TypeError) as error:
            return render(request, 'alerts/condition_form.html', {
                'indicators': indicators,
                'operators': AlertCondition.OPERATOR_CHOICES,
                'error': str(error),
            })

    return render(request, 'alerts/condition_form.html', {
        'indicators': indicators,
        'operators': AlertCondition.OPERATOR_CHOICES,
    })
