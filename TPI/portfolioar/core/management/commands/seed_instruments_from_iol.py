import urllib.parse

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.currency import normalize_iol_currency
from core.models import Broker, Stock
from portfolio.data_access import _get_iol_token

# (instrumento, panel, tipo) según los nombres que acepta /api/v2/Cotizaciones/{instrumento}/{panel}/{pais}.
# No hay un endpoint de IOL que liste los paneles disponibles: se relevaron a mano probando contra la API real.
PANELS = [
    ('Acciones', 'Panel General', 'accion'),
    # En la web se muestra como "Panel Líderes"; la API lo expone como "Merval".
    ('Acciones', 'Merval', 'accion'),
    ('Acciones', 'CEDEARs', 'cedear'),
    ('Bonos', 'Publica Nacional', 'bono'),
    ('Bonos', 'Soberanos en Dolar', 'bono'),
    ('Letras', 'Todas', 'letra'),
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
        'Importa el catálogo de instrumentos (acciones, cedears, bonos y letras) desde la API de IOL '
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

        # Obtener todos los paneles antes de escribir instrumentos: si IOL falla a mitad,
        # no deja un catálogo parcial que haga creer al seed de demo que ya terminó.
        catalogs = []
        currencies_by_ticker = {}
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
                currency = normalize_iol_currency(titulo.get('moneda'))
                if currency is None:
                    raise CommandError(f'Moneda de negociación desconocida para {ticker}: {titulo.get("moneda")!r}')
                previous = currencies_by_ticker.get(ticker)
                if previous is not None and previous != currency:
                    raise CommandError(f'Los paneles de IOL informan monedas distintas para {ticker}')
                currencies_by_ticker[ticker] = currency
                catalogs.append((titulo, tipo, currency))

        created_count = 0
        updated_count = 0
        with transaction.atomic():
            for titulo, tipo, currency in catalogs:
                ticker = titulo.get('simbolo')
                if not ticker:
                    continue
                company_name = titulo.get('descripcion') or ticker
                stock, created = Stock.objects.get_or_create(
                    ticker=ticker,
                    defaults={'company_name': company_name, 'tipo': tipo, 'trading_currency': currency},
                )
                if created:
                    created_count += 1
                    continue
                changed = []
                if stock.tipo != tipo:
                    stock.tipo = tipo
                    changed.append('tipo')
                if stock.trading_currency != currency:
                    stock.trading_currency = currency
                    changed.append('trading_currency')
                if not stock.company_name and company_name:
                    stock.company_name = company_name
                    changed.append('company_name')
                if changed:
                    stock.save(update_fields=changed)
                    updated_count += 1

        # El catálogo IAMC versionado se aplica también a la importación nueva; lo
        # que no esté respaldado por esa fuente permanece sin clasificar.
        from django.core.management import call_command
        call_command('sync_instrument_classification', apply=True, stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            f'{created_count} instrumentos nuevos y {updated_count} existentes actualizados desde IOL.'
        ))
