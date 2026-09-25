from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .business import AlertManager, IndicatorManager, ConditionManager
from .models import AlertCondition
from core.business import StockManager


def _alert_form_context(**extra):
    stock_manager = StockManager()
    return {
        'stocks': stock_manager.get_all(),
        'stock_types': stock_manager.get_type_choices(),
        'indicators': IndicatorManager().get_all(),
        'operators': AlertCondition.OPERATOR_CHOICES,
        **extra,
    }


@login_required
def alert_list(request):
    alert_manager = AlertManager()
    alerts = alert_manager.get_user_alerts(request.user.id)

    return render(request, 'alerts/alert_list.html', {'alerts': alerts})


@login_required
def alert_detail(request, alert_id):
    alert_manager = AlertManager()
    alert = alert_manager.get_alert(alert_id, request.user.id)
    assigned_conditions = alert_manager.get_alert_conditions(alert)
    triggers = alert_manager.get_alert_triggers(alert_id)

    return render(request, 'alerts/alert_detail.html', {
        'alert': alert,
        'assigned_conditions': assigned_conditions,
        'triggers': triggers,
        'stocks': StockManager().get_all(),
        'stock_types': StockManager().get_type_choices(),
        'indicators': IndicatorManager().get_all(),
        'operators': AlertCondition.OPERATOR_CHOICES,
    })


@login_required
def alert_create(request):
    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        name = request.POST.get('name')
        is_active = request.POST.get('is_active') == 'on'
        indicator_id = request.POST.get('indicator_id')
        operator = request.POST.get('operator')

        try:
            alert_manager = AlertManager()
            threshold_value = Decimal(request.POST.get('threshold_value'))
            alert = alert_manager.create_alert_with_condition(
                request.user.id, stock_id, name, indicator_id, operator, threshold_value, is_active
            )
            return redirect('alerts:alert_detail', alert_id=alert.id)
        except (ValueError, InvalidOperation, TypeError, ObjectDoesNotExist) as error:
            return render(request, 'alerts/alert_form.html', _alert_form_context(
                error=str(error), form_data=request.POST
            ))

    return render(request, 'alerts/alert_form.html', _alert_form_context(form_data={'is_active': 'on'}))


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
            messages.error(request, str(e))
            return redirect('alerts:alert_detail', alert_id=alert_id)

    return redirect('alerts:alert_detail', alert_id=alert_id)


@login_required
@require_POST
def alert_delete(request, alert_id):
    alert_manager = AlertManager()
    alert_manager.get_alert(alert_id, request.user.id)
    alert_manager.delete_alert(alert_id)
    return redirect('alerts:alert_list')


@login_required
@require_POST
def alert_create_condition(request, alert_id):
    alert_manager = AlertManager()
    alert_manager.get_alert(alert_id, request.user.id)
    try:
        threshold_value = Decimal(request.POST.get('threshold_value'))
        alert_manager.create_and_add_condition(
            alert_id,
            request.POST.get('indicator_id'),
            request.POST.get('operator'),
            threshold_value,
        )
    except (ValueError, InvalidOperation, TypeError, ObjectDoesNotExist) as error:
        messages.error(request, f'No se pudo crear la condición: {error}')
    return redirect('alerts:alert_detail', alert_id=alert_id)



@login_required
@require_POST
def alert_remove_condition(request, alert_id, condition_id):
    alert_manager = AlertManager()
    alert_manager.get_alert(alert_id, request.user.id)
    try:
        alert_manager.remove_condition(alert_id, condition_id)
    except ValueError as error:
        messages.error(request, str(error))
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
