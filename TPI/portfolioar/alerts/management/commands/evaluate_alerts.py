from django.core.management.base import BaseCommand

from alerts.business import AlertManager


class Command(BaseCommand):
    help = 'Evalúa una vez todas las alertas activas y registra sus disparos.'

    def handle(self, *args, **options):
        stats = AlertManager().evaluate_active_alerts()
        self.stdout.write(self.style.SUCCESS(
            'Evaluación finalizada: '
            f"{stats['evaluated']} evaluadas, "
            f"{stats['triggered']} disparadas, "
            f"{stats['cooldown']} en cooldown, "
            f"{stats['skipped']} omitidas, "
            f"{stats['errors']} errores."
        ))
