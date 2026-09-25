from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import Stock, Broker
from portfolio.models import CashPosition

DEMO_EMAIL = 'demo@test.com'
DEMO_PASSWORD = 'demo1234'
DEMO_CASH_ARS = 5_000_000
DEMO_CASH_USD = 5_000


class Command(BaseCommand):
    help = 'Crea (o resetea) un usuario de demo con liquidez inicial para desarrollo local. Idempotente.'

    def handle(self, *args, **options):
        if not Stock.objects.exists() and not Broker.objects.exists():
            call_command('seed_instruments_from_iol', stdout=self.stdout)

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={'first_name': 'Demo', 'last_name': 'User'},
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'Creado' if created else 'Actualizado'} usuario demo: {DEMO_EMAIL} / {DEMO_PASSWORD}"
        ))

        for currency, amount in [('ARS', DEMO_CASH_ARS), ('USD', DEMO_CASH_USD)]:
            _, cash_created = CashPosition.objects.get_or_create(
                user=user,
                currency=currency,
                description='Seed inicial',
                defaults={'amount': amount},
            )
            if cash_created:
                self.stdout.write(self.style.SUCCESS(f"Liquidez inicial {currency} {amount} cargada"))
            else:
                self.stdout.write(f"Liquidez {currency} ya existía, no se duplicó")

        call_command('seed_technical_indicators', stdout=self.stdout)
