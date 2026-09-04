from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0002_cash_position'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='position',
            name='status',
            field=models.CharField(choices=[('open', 'Abierta'), ('closed', 'Cerrada')], default='open', max_length=6),
        ),
        migrations.AddField(
            model_name='position',
            name='opened_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name='Lot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField()),
                ('price_local', models.DecimalField(decimal_places=4, max_digits=15)),
                ('price_usd', models.DecimalField(decimal_places=4, max_digits=15)),
                ('purchased_at', models.DateTimeField()),
                ('purchase_currency', models.CharField(choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')], default='ARS', max_length=3)),
                ('fees', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to='portfolio.position')),
            ],
            options={
                'verbose_name': 'lote',
                'verbose_name_plural': 'lotes',
                'db_table': 'lot',
                'ordering': ['purchased_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='Sale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.IntegerField()),
                ('price_local', models.DecimalField(decimal_places=4, max_digits=15)),
                ('price_usd', models.DecimalField(decimal_places=4, max_digits=15)),
                ('sold_at', models.DateTimeField()),
                ('sell_currency', models.CharField(choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')], default='ARS', max_length=3)),
                ('realized_pnl_ars', models.DecimalField(decimal_places=4, max_digits=18)),
                ('realized_pnl_usd', models.DecimalField(decimal_places=4, max_digits=18)),
                ('position', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sales', to='portfolio.position')),
            ],
            options={
                'verbose_name': 'venta',
                'verbose_name_plural': 'ventas',
                'db_table': 'sale',
                'ordering': ['-sold_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='SaleLot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount_consumed', models.IntegerField()),
                ('cost_price_local', models.DecimalField(decimal_places=4, max_digits=15)),
                ('cost_price_usd', models.DecimalField(decimal_places=4, max_digits=15)),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sale_lots', to='portfolio.lot')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumed_lots', to='portfolio.sale')),
            ],
            options={
                'verbose_name': 'lote de venta',
                'verbose_name_plural': 'lotes de venta',
                'db_table': 'sale_lot',
            },
        ),
        migrations.CreateModel(
            name='CashTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency', models.CharField(choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')], max_length=3)),
                ('amount', models.DecimalField(decimal_places=4, max_digits=18)),
                ('tipo', models.CharField(choices=[('compra', 'Compra'), ('recupero', 'Recupero')], max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('position', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cash_transactions', to='portfolio.position')),
                ('lot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cash_transactions', to='portfolio.lot')),
                ('sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cash_transactions', to='portfolio.sale')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cash_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'cash_transaction',
                'ordering': ['-created_at'],
            },
        ),
    ]
