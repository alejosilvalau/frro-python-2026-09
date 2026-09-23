from django.core.management.base import BaseCommand

from alerts.business import IndicatorManager


class Command(BaseCommand):
    help = 'Crea o actualiza el catálogo de indicadores técnicos de forma idempotente.'

    def handle(self, *args, **options):
        stats = IndicatorManager().seed_defaults()
        self.stdout.write(self.style.SUCCESS(
            f"Indicadores listos: {stats['created']} creados, {stats['existing']} existentes."
        ))
