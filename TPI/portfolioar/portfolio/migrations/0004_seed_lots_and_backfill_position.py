from django.db import migrations


def seed_lots(apps, schema_editor):
    Position = apps.get_model('portfolio', 'Position')
    Order = apps.get_model('portfolio', 'Order')
    Lot = apps.get_model('portfolio', 'Lot')
    CashTransaction = apps.get_model('portfolio', 'CashTransaction')

    for position in Position.objects.all():
        lot = Lot.objects.create(
            position=position,
            amount=position.amount,
            price_local=position.stock_price_local,
            price_usd=position.stock_price_usd,
            purchased_at=position.purchased_at,
            purchase_currency='ARS',
            fees=0,
        )
        CashTransaction.objects.create(
            user=position.user,
            currency='ARS',
            amount=lot.amount * lot.price_local,
            tipo='compra',
            position=position,
            lot=lot,
        )
        position.opened_at = position.purchased_at
        position.status = 'open'
        position.save(update_fields=['opened_at', 'status'])

    for order in Order.objects.all():
        lot = Lot.objects.create(
            position=order.position,
            amount=order.amount,
            price_local=order.price_local,
            price_usd=order.price_usd,
            purchased_at=order.fulfill_datetime,
            purchase_currency='ARS',
            fees=order.total_fees,
        )
        CashTransaction.objects.create(
            user=order.position.user,
            currency='ARS',
            amount=lot.amount * lot.price_local,
            tipo='compra',
            position=order.position,
            lot=lot,
        )


def reverse_seed(apps, schema_editor):
    Lot = apps.get_model('portfolio', 'Lot')
    CashTransaction = apps.get_model('portfolio', 'CashTransaction')
    CashTransaction.objects.filter(tipo='compra').delete()
    Lot.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0003_lot_sale_cashtransaction'),
    ]

    operations = [
        migrations.RunPython(seed_lots, reverse_seed),
    ]
