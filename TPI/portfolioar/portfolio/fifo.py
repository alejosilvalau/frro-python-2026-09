from collections import namedtuple
from decimal import Decimal

LotConsumption = namedtuple('LotConsumption', ['lot', 'amount_consumed', 'cost_price_local', 'cost_price_usd'])


def get_open_lots(lots, sale_lots):
    """lots: iterable[Lot] ordenados FIFO (purchased_at, id) ascendente.
    sale_lots: iterable[SaleLot] asociados a esos lotes (cualquier orden).
    Devuelve list[(lot, remaining_amount)] con remaining_amount > 0, en orden FIFO."""
    consumed_by_lot = {}
    for sl in sale_lots:
        consumed_by_lot[sl.lot_id] = consumed_by_lot.get(sl.lot_id, 0) + sl.amount_consumed

    open_lots = []
    for lot in lots:
        remaining = lot.amount - consumed_by_lot.get(lot.id, 0)
        if remaining > 0:
            open_lots.append((lot, remaining))
    return open_lots


def compute_sale_consumption(open_lots, amount_to_sell):
    """open_lots: list[(lot, remaining_amount)] en orden FIFO.
    Devuelve list[LotConsumption]. Lanza ValueError si amount_to_sell <= 0
    o supera la cantidad total disponible."""
    if amount_to_sell <= 0:
        raise ValueError("La cantidad a vender debe ser mayor a 0")

    total_available = sum(remaining for _, remaining in open_lots)
    if amount_to_sell > total_available:
        raise ValueError(
            f"No hay suficientes acciones disponibles. Disponible: {total_available} — Solicitado: {amount_to_sell}"
        )

    consumptions = []
    to_consume = amount_to_sell
    for lot, remaining in open_lots:
        if to_consume <= 0:
            break
        consume = min(remaining, to_consume)
        consumptions.append(LotConsumption(lot, consume, lot.price_local, lot.price_usd))
        to_consume -= consume

    return consumptions


def compute_realized_pnl(consumptions, sell_price_local, sell_price_usd):
    """Devuelve (realized_pnl_ars, realized_pnl_usd, total_cost_local, total_cost_usd)."""
    total_cost_local = sum(Decimal(str(c.cost_price_local)) * c.amount_consumed for c in consumptions)
    total_cost_usd = sum(Decimal(str(c.cost_price_usd)) * c.amount_consumed for c in consumptions)
    total_amount = sum(c.amount_consumed for c in consumptions)

    proceeds_local = Decimal(str(sell_price_local)) * total_amount
    proceeds_usd = Decimal(str(sell_price_usd)) * total_amount

    realized_pnl_ars = proceeds_local - total_cost_local
    realized_pnl_usd = proceeds_usd - total_cost_usd

    return realized_pnl_ars, realized_pnl_usd, total_cost_local, total_cost_usd


def compute_weighted_avg_cost(open_lots):
    """Devuelve (avg_cost_local, avg_cost_usd, total_open_amount); (0,0,0) si no hay lotes abiertos."""
    total_open_amount = sum(remaining for _, remaining in open_lots)
    if total_open_amount == 0:
        return Decimal('0'), Decimal('0'), 0

    total_cost_local = sum(Decimal(str(lot.price_local)) * remaining for lot, remaining in open_lots)
    total_cost_usd = sum(Decimal(str(lot.price_usd)) * remaining for lot, remaining in open_lots)

    avg_cost_local = total_cost_local / total_open_amount
    avg_cost_usd = total_cost_usd / total_open_amount
    return avg_cost_local, avg_cost_usd, total_open_amount
