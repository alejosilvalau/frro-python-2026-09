from django.shortcuts import get_object_or_404

from .models import Position, Order
from core.data_access import get_user_by_id, get_stock_by_id, get_broker_by_id


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
