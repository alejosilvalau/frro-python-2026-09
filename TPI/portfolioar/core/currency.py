import unicodedata


def normalize_iol_currency(value):
    """Translate a known IOL quote currency without guessing unknown values."""
    raw = unicodedata.normalize('NFKD', str(value or '').casefold())
    normalized = ''.join(char for char in raw if not unicodedata.combining(char))
    normalized = normalized.replace('_', '').replace(' ', '').strip()
    if normalized in {'ar$', 'ars', 'pesoargentino', 'pesosargentinos'}:
        return 'ARS'
    if normalized in {'us$', 'u$s', 'usd', 'dolarestadounidense', 'dolaresestadounidenses'}:
        return 'USD'
    return None
