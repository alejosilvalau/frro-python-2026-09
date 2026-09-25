from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0009_backfill_legacy_pricing')]

    operations = [
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.CheckConstraint(condition=Q(quote_unit__in=[1, 100]), name='lot_quote_unit_valid'),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.CheckConstraint(condition=Q(ccl_rate__isnull=True) | Q(ccl_rate__gt=0), name='lot_ccl_positive'),
        ),
        migrations.AddConstraint(
            model_name='lot',
            constraint=models.CheckConstraint(condition=Q(price_origin='legacy') | Q(ccl_rate__isnull=False), name='lot_nonlegacy_requires_ccl'),
        ),
        migrations.AddConstraint(
            model_name='sale',
            constraint=models.CheckConstraint(condition=Q(quote_unit__in=[1, 100]), name='sale_quote_unit_valid'),
        ),
        migrations.AddConstraint(
            model_name='sale',
            constraint=models.CheckConstraint(condition=Q(ccl_rate__isnull=True) | Q(ccl_rate__gt=0), name='sale_ccl_positive'),
        ),
        migrations.AddConstraint(
            model_name='sale',
            constraint=models.CheckConstraint(condition=Q(price_origin='legacy') | Q(ccl_rate__isnull=False), name='sale_nonlegacy_requires_ccl'),
        ),
    ]
