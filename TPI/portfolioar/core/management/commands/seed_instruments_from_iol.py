import urllib.parse

import requests
from django.core.management.base import BaseCommand, CommandError

from core.models import Broker, Stock
from portfolio.data_access import _get_iol_token

# (instrumento, panel, tipo) según los nombres que acepta /api/v2/Cotizaciones/{instrumento}/{panel}/{pais}.
# No hay un endpoint de IOL que liste los paneles disponibles: se relevaron a mano probando contra la API real.
PANELS = [
    ('Acciones', 'Panel General', 'accion'),
    ('Acciones', 'CEDEARs', 'cedear'),
    ('Bonos', 'Publica Nacional', 'bono'),
    ('Bonos', 'Soberanos en Dolar', 'bono'),
]

# Los brokers no salen de IOL (son las plataformas donde el usuario opera, no instrumentos): se siembran fijos.
BROKERS = [
    ('InvertirOnline (IOL)', 'https://www.invertironline.com'),
    ('Balanz', 'https://balanz.com'),
    ('Portfolio Personal (PPI)', 'https://www.portfoliopersonal.com'),
    ('Primary', 'https://www.primary.com.ar'),
]


class Command(BaseCommand):
    help = (
        'Importa el catálogo de instrumentos (acciones, cedears, bonos) desde la API de IOL '
        'y siembra los brokers fijos. Idempotente (get_or_create por ticker/nombre). '
        'Requiere IOL_USER/IOL_PASSWORD configurados.'
    )

    def handle(self, *args, **options):
        for name, link in BROKERS:
            _, created = Broker.objects.get_or_create(name=name, defaults={'link': link})
            if created:
                self.stdout.write(self.style.SUCCESS(f'Broker creado: {name}'))

        try:
            token = _get_iol_token()
        except Exception as exc:
            raise CommandError(f'No se pudo autenticar contra IOL: {exc}')

        created_count = 0
        for instrumento, panel, tipo in PANELS:
            url = (
                'https://api.invertironline.com/api/v2/Cotizaciones/'
                f'{urllib.parse.quote(instrumento)}/{urllib.parse.quote(panel)}/argentina'
            )
            resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=15)
            resp.raise_for_status()
            for titulo in resp.json().get('titulos', []):
                ticker = titulo.get('simbolo')
                if not ticker:
                    continue
                company_name = titulo.get('descripcion') or ticker
                _, created = Stock.objects.get_or_create(
                    ticker=ticker,
                    defaults={'company_name': company_name, 'tipo': tipo},
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f'{created_count} instrumentos nuevos importados desde IOL.'))
