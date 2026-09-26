import csv
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Sector, Stock


FIELDS = (
    'sector', 'cedear_kind', 'issuer_type', 'rate_reference', 'payment_style',
    'instrument_family', 'underlying_ticker',
)
SECTOR_ALIASES = {
    'consumo basico': 'Consumo',
    'consumo básico': 'Consumo',
    'consumo discrecional': 'Consumo',
    'energia': 'Energía',
    'energía': 'Energía',
    'finanzas': 'Finanzas',
    'servicios financieros': 'Finanzas',
    'materiales': 'Materiales',
    'salud': 'Salud',
    'tecnologia': 'Tecnología',
    'tecnología': 'Tecnología',
    'tecnología de la información': 'Tecnología',
    'comunicaciones': 'Comunicaciones',
    'servicios publicos': 'Servicios Públicos',
    'servicios públicos': 'Servicios Públicos',
    'bienes raices': 'Bienes Raíces',
}


def classify_fixed_income_description(stock):
    """Return only classifications explicitly named by a known instrument family/issuer."""
    if stock.tipo not in {'bono', 'letra'}:
        return {}
    text = unicodedata.normalize('NFKD', f'{stock.ticker} {stock.company_name}').encode(
        'ascii', 'ignore'
    ).decode().upper()
    family = next((
        name for name in ('BOPREAL', 'LECAP', 'BONCAP', 'BONCER', 'LEDES', 'LELINK', 'BONO TAMAR')
        if name in text
    ), '')
    result = {}
    if family == 'BOPREAL':
        result['issuer_type'] = 'bcra'
    elif re.search(r'\b(MUN|MUNICIPAL|MUNIC)\b', text):
        result['issuer_type'] = 'municipal'
    elif re.search(r'\b(PCIA|PROVINCIA|PROV)\b', text):
        result['issuer_type'] = 'provincial'
    elif family or re.search(r'REP\.?\s*(ARG|ARGENTINA)|TESORO\s*(NAC|NACIONAL)', text):
        result['issuer_type'] = 'national'
    elif re.search(r'FIDEICOMISO|FIDEICOMISARIO|\bFF\b', text):
        result['issuer_type'] = 'trust'

    family_fields = {
        'LECAP': ('fixed', 'capitalizable'),
        'BONCAP': ('fixed', 'capitalizable'),
        'BONCER': ('cer', ''),
        'LEDES': ('fixed', 'discount'),
        'LELINK': ('dollar_linked', 'discount'),
        'BONO TAMAR': ('tamar', ''),
    }
    if family in family_fields:
        result['instrument_family'] = family
        rate, style = family_fields[family]
        result['rate_reference'] = rate
        if style:
            result['payment_style'] = style
    elif 'TAMAR' in text:
        result['rate_reference'] = 'tamar'
    elif 'DOLAR LINKED' in text or 'DOLLAR LINKED' in text:
        result['rate_reference'] = 'dollar_linked'
    elif 'DUAL' in text:
        result['rate_reference'] = 'dual'
    elif 'CER' in text:
        result['rate_reference'] = 'cer'
    elif 'STEP UP' in text:
        result.update(rate_reference='fixed', payment_style='step_up')
    elif re.search(r'\bTASA FIJA\b|\d+(?:[.,]\d+)?\s*%', text):
        result['rate_reference'] = 'fixed'

    if not result.get('payment_style') and re.search(r'\bCAP(?:ITALIZABLE)?\b', text):
        result['payment_style'] = 'capitalizable'
    return result


class Command(BaseCommand):
    help = (
        'Sincroniza metadatos desde un catálogo CSV revisado. Por defecto solo simula; '
        'usar --apply para guardar cambios.'
    )

    def add_arguments(self, parser):
        default_catalog = Path(__file__).resolve().parents[2] / 'data' / 'instrument_classification.csv'
        parser.add_argument('--catalog', default=str(default_catalog))
        parser.add_argument('--apply', action='store_true', help='Aplica los cambios a la base.')

    def handle(self, *args, **options):
        path = Path(options['catalog'])
        if not path.is_file():
            raise CommandError(f'No existe el catálogo: {path}')

        with path.open(newline='', encoding='utf-8-sig') as catalog_file:
            reader = csv.DictReader(catalog_file)
            rows = list(reader)
        required = {'ticker', 'tipo', 'source', 'source_date', *FIELDS}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise CommandError(f'El CSV debe incluir estas columnas: {", ".join(sorted(required))}')

        stats = Counter()
        conflicts = set()
        missing = set()
        planned = []
        stats['catalog_rows'] = len(rows)
        catalog_tickers = {
            (row['ticker'].strip().upper(), row['tipo'].strip()) for row in rows
        }
        for row in rows:
            ticker = row['ticker'].strip().upper()
            stock = Stock.objects.filter(ticker__iexact=ticker, tipo=row['tipo'].strip()).first()
            if stock is None:
                stats['not_found'] += 1
                missing.add(f'{ticker} ({row["tipo"].strip()})')
                continue
            source_date = date.fromisoformat(row['source_date'].strip())
            targets = [stock]
            # IAMC publica la especie base. C y D son variantes de moneda del mismo
            # CEDEAR (CCL y dólar oficial); la relación se forma por ticker completo,
            # nunca quitando un sufijo arbitrario. IOL puede truncar las descripciones.
            if stock.tipo == 'cedear' and row.get('cedear_kind', '').strip() in {'company', 'etf'}:
                variants = Stock.objects.filter(
                    tipo='cedear',
                    ticker__in=(f'{stock.ticker}C', f'{stock.ticker}D'),
                )
                targets = [stock]
                for variant in variants:
                    # A CEDEAR ticker present in IAMC is its own species, not a
                    # C/D suffix of another instrument (e.g. BBD vs BB + D).
                    if (variant.ticker, 'cedear') in catalog_tickers:
                        continue
                    if variant.underlying_ticker and variant.underlying_ticker != stock.ticker:
                        stats['protected_or_conflicting'] += 1
                        conflicts.add(
                            f'{variant.ticker}: subyacente {variant.underlying_ticker} != {stock.ticker}'
                        )
                        continue
                    targets.append(variant)
            for target in targets:
                updates = {}
                for field in FIELDS:
                    value = row.get(field, '').strip()
                    if field == 'sector':
                        if not value or target.tipo not in {'accion', 'cedear'}:
                            continue
                        value = SECTOR_ALIASES.get(value.casefold(), value.strip())
                        if value.casefold() == 'soberano':
                            stats['invalid_sector'] += 1
                            continue
                        current_value = target.sector_id
                        if target.classification_manual:
                            stats['protected_or_conflicting'] += 1
                            conflicts.add(f'{target.ticker}: manual')
                            continue
                        if current_value and target.sector.name != value:
                            stats['protected_or_conflicting'] += 1
                            conflicts.add(f'{target.ticker}: sector {target.sector.name} != {value}')
                            continue
                        sector = Sector.objects.filter(name=value).first()
                        if sector is None or target.sector_id != sector.id:
                            updates['sector'] = value
                    else:
                        if not value:
                            continue
                        current_value = getattr(target, field)
                        if target.classification_manual:
                            stats['protected_or_conflicting'] += 1
                            conflicts.add(f'{target.ticker}: manual')
                            continue
                        if current_value != value:
                            updates[field] = value
                if stock.tipo == 'cedear' and not target.classification_manual and not target.underlying_ticker:
                    updates['underlying_ticker'] = stock.ticker
                if updates:
                    updates['classification_source'] = row['source'].strip()
                    updates['classification_date'] = source_date
                    planned.append((target, updates))
                    stats['instruments_to_update'] += 1
                    stats['fields_to_update'] += len(updates) - 2
                else:
                    stats['unchanged'] += 1

        planned_by_id = {stock.id: updates for stock, updates in planned}
        for stock in Stock.objects.filter(tipo__in=('bono', 'letra')):
            rule_fields = classify_fixed_income_description(stock)
            if not rule_fields:
                continue
            updates = dict(planned_by_id.get(stock.id, {}))
            changed = False
            for field, value in rule_fields.items():
                if stock.classification_manual:
                    stats['protected_or_conflicting'] += 1
                    conflicts.add(f'{stock.ticker}: manual')
                    continue
                catalog_value = updates.get(field)
                current_value = getattr(stock, field)
                if catalog_value and catalog_value != value:
                    stats['protected_or_conflicting'] += 1
                    conflicts.add(f'{stock.ticker}: catalog {field}={catalog_value} != rule {value}')
                elif not catalog_value and current_value not in (None, '') and current_value != value:
                    stats['protected_or_conflicting'] += 1
                    conflicts.add(f'{stock.ticker}: {field}={current_value} != rule {value}')
                elif not catalog_value and current_value != value:
                    updates[field] = value
                    changed = True
            if changed:
                updates.setdefault('classification_source', 'Regla determinista sobre descripción IOL')
                updates.setdefault('classification_date', date.today())
                planned_by_id[stock.id] = updates
        planned = [
            (stock, planned_by_id[stock.id])
            for stock in Stock.objects.filter(id__in=planned_by_id)
        ]
        stats['instruments_to_update'] = len(planned)
        stats['fields_to_update'] = sum(len(updates) - 2 for _, updates in planned)

        if options['apply']:
            with transaction.atomic():
                for stock, updates in planned:
                    for field, value in updates.items():
                        if field == 'sector':
                            value, _ = Sector.objects.get_or_create(name=value)
                        setattr(stock, field, value)
                    stock.save(update_fields=list(updates))
            action = 'Aplicado'
        else:
            action = 'Simulación (sin escrituras)'

        planned_by_id = {stock.id: updates for stock, updates in planned}
        coverage = Counter()
        for stock in Stock.objects.select_related('sector'):
            updates = planned_by_id.get(stock.id, {})
            sector_assigned = 'sector' in updates or stock.sector_id is not None
            kind_assigned = updates.get('cedear_kind', stock.cedear_kind)
            issuer_assigned = updates.get('issuer_type', stock.issuer_type)
            if stock.tipo == 'accion':
                coverage['actions_total'] += 1
                coverage['actions_sector'] += bool(sector_assigned)
            elif stock.tipo == 'cedear':
                coverage['cedears_total'] += 1
                coverage['cedears_classified'] += bool(kind_assigned)
                coverage['cedears_sector'] += bool(
                    kind_assigned == 'company' and (sector_assigned or stock.sector_id)
                )
            elif stock.tipo in {'bono', 'letra'}:
                coverage['fixed_income_total'] += 1
                coverage['fixed_income_issuer'] += bool(issuer_assigned)

        self.stdout.write(
            f'{action}: {stats["catalog_rows"]} filas de catálogo; '
            f'{stats["instruments_to_update"]} instrumentos, '
            f'{stats["fields_to_update"]} campos; '
            f'{stats["unchanged"]} sin cambios; {stats["not_found"]} ticker/tipo no encontrados; '
            f'{stats["protected_or_conflicting"]} protegidos o en conflicto; '
            f'{stats["invalid_sector"]} sectores rechazados.'
        )
        self.stdout.write(
            'Cobertura proyectada (clasificados/total): '
            f'acciones con sector {coverage["actions_sector"]}/{coverage["actions_total"]}; '
            f'CEDEARs empresa/ETF {coverage["cedears_classified"]}/{coverage["cedears_total"]} '
            f'(sector empresarial {coverage["cedears_sector"]}); '
            f'renta fija con emisor {coverage["fixed_income_issuer"]}/{coverage["fixed_income_total"]}.'
        )
        if conflicts:
            self.stdout.write(f'Conflictos/manuales preservados: {", ".join(sorted(conflicts)[:20])}')
        if missing:
            self.stdout.write(f'Filas del catálogo sin instrumento IOL: {", ".join(sorted(missing)[:20])}')
