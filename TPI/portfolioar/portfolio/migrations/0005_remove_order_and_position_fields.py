from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0004_seed_lots_and_backfill_position'),
    ]

    operations = [
        migrations.RemoveField(model_name='position', name='amount'),
        migrations.RemoveField(model_name='position', name='stock_price_local'),
        migrations.RemoveField(model_name='position', name='stock_price_usd'),
        migrations.RemoveField(model_name='position', name='purchased_at'),
        migrations.DeleteModel(name='Order'),
        migrations.AlterField(
            model_name='position',
            name='status',
            field=models.CharField(choices=[('open', 'Abierta'), ('closed', 'Cerrada')], default='open', max_length=6),
        ),
        migrations.AlterField(
            model_name='position',
            name='opened_at',
            field=models.DateTimeField(),
        ),
        migrations.AlterModelOptions(
            name='position',
            options={'ordering': ['-opened_at'], 'verbose_name': 'posición', 'verbose_name_plural': 'posiciones'},
        ),
    ]
