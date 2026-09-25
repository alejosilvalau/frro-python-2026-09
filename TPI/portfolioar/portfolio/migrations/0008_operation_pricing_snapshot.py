# Generated manually for the historical-operation pricing snapshot.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0007_separate_cash_transaction_types')]

    operations = [
        *[
            migrations.AddField(
                model_name=model_name,
                name=name,
                field=field,
            )
            for model_name in ('lot', 'sale')
            for name, field in (
                ('price_input_currency', models.CharField(choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')], default='ARS', max_length=3)),
                ('price_origin', models.CharField(choices=[('auto', 'Automático'), ('manual', 'Manual'), ('legacy', 'Registro previo')], default='legacy', max_length=6)),
                ('price_source', models.CharField(choices=[('iol_realtime', 'IOL tiempo real'), ('iol_daily_close', 'IOL cierre diario'), ('manual', 'Manual'), ('legacy', 'Registro previo')], default='legacy', max_length=20)),
                ('price_quote_date', models.DateField(blank=True, null=True)),
                ('quote_currency', models.CharField(blank=True, choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')], max_length=3, null=True)),
                ('quote_unit', models.PositiveSmallIntegerField(default=1)),
                ('ccl_rate', models.DecimalField(blank=True, decimal_places=4, max_digits=15, null=True)),
                ('ccl_date', models.DateField(blank=True, null=True)),
                ('ccl_source', models.CharField(choices=[('argentinadatos', 'ArgentinaDatos'), ('manual', 'Manual'), ('legacy_implied', 'CCL implícito de registro previo')], default='legacy_implied', max_length=20)),
            )
        ],
    ]
