from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_stock_cedear_kind_stock_classification_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='stock',
            name='trading_currency',
            field=models.CharField(
                blank=True, choices=[('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')],
                max_length=3, null=True,
            ),
        ),
    ]
