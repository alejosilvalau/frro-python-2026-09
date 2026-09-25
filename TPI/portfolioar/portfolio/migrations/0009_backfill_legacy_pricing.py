from django.db import migrations


def backfill_legacy_pricing(apps, schema_editor):
    for model_name, currency_field in (('Lot', 'purchase_currency'), ('Sale', 'sell_currency')):
        model = apps.get_model('portfolio', model_name)
        for operation in model.objects.all().iterator():
            implied_ccl = None
            if operation.price_usd:
                implied_ccl = operation.price_local / operation.price_usd
            model.objects.filter(pk=operation.pk).update(
                price_input_currency=getattr(operation, currency_field),
                price_origin='legacy',
                price_source='legacy',
                quote_unit=1,
                ccl_rate=implied_ccl,
                ccl_source='legacy_implied',
            )


def reverse_backfill(apps, schema_editor):
    for model_name in ('Lot', 'Sale'):
        model = apps.get_model('portfolio', model_name)
        model.objects.all().update(ccl_rate=None, ccl_date=None, price_quote_date=None)


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0008_operation_pricing_snapshot')]

    operations = [migrations.RunPython(backfill_legacy_pricing, reverse_backfill)]
