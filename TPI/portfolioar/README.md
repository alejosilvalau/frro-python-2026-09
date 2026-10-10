# PortfolioAR

Django 5.2 — gestión de portafolio (acciones, CEDEARs, bonos, letras), liquidez en ARS/USD y alertas técnicas.

## Requisitos

- Python 3.10+ (probado en 3.12)
- SQLite para desarrollo local (`USE_SQLITE=True`, sin dependencias extra)
- SQL Server + `ODBC Driver 18 for SQL Server` solo si `USE_SQLITE=False`

## Puesta en marcha

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # editar: USE_SQLITE=True para local
python manage.py migrate
python manage.py runserver  # http://127.0.0.1:8000/
```

Variables clave en `.env` (ver `.env.example`):
`USE_SQLITE`, `DB_NAME/USER/PASSWORD/HOST/PORT` (solo MSSQL),
`DJANGO_SECRET_KEY/DEBUG/ALLOWED_HOSTS`, `IOL_USER/IOL_PASSWORD` (precios IOL).

## Comandos propios

Todos idempotentes salvo indicación. Se ejecutan como `python manage.py <comando>`.

| Comando | Qué hace | Ejemplo |
|---|---|---|
| `seed_example_data` | Carga datos de ejemplo con las validaciones de la app: monedas de negociación, depósitos ARS/USD, posiciones GGAL/MSFT, lote extra, venta parcial, retiro de ejemplo, indicadores y alerta RSI. Omite lo que ya existe. | `python manage.py seed_example_data` · `--username alejo --ccl 1400` |
| `seed_demo_data` | Crea/resetea usuario demo `demo@test.com` / `demo1234` con liquidez inicial + indicadores. | `python manage.py seed_demo_data` |
| `seed_instruments_from_iol` | Importa catálogo de instrumentos + brokers fijos desde la API de IOL. Requiere `IOL_USER/IOL_PASSWORD`. | `python manage.py seed_instruments_from_iol` |
| `sync_instrument_classification` | Sincroniza metadatos (sector, tipo, emisor) desde `core/data/instrument_classification.csv`. Por defecto simula. | `python manage.py sync_instrument_classification --apply` |
| `seed_technical_indicators` | Crea/actualiza el catálogo de indicadores (RSI, MACD, SMA…): 7 por defecto. | `python manage.py seed_technical_indicators` |
| `evaluate_alerts` | Evalúa una vez las alertas activas y registra disparos (respeta cooldown de 15 min). | `python manage.py evaluate_alerts` |

Orden sugerido para una base con ejemplos:

```bash
python manage.py migrate
python manage.py seed_technical_indicators
python manage.py seed_example_data          # usa --username <tu_usuario>
python manage.py evaluate_alerts
```

## Comandos Django útiles

```bash
python manage.py check                    # validación sin tocar la DB
python manage.py createsuperuser          # usuario admin (/admin/)
python manage.py changepassword <usuario> # recuperar acceso
python manage.py shell                    # consola ORM
pytest                                    # 199 tests (SQLite en memoria)
```

## Problemas comunes

- **Dashboard muestra "No disponible" en rendimientos**: suele ser catálogo
  desactualizado (al instrumento le falta la moneda de negociación).
  Actualizar con `python manage.py seed_instruments_from_iol`
  (requiere `IOL_USER`/`IOL_PASSWORD` en `.env`). Un fin de semana o feriado
  usa automáticamente el último valor disponible.

## Rutas principales

`/auth/register/` · `/auth/login/` · `/portfolio/` (dashboard) ·
`/portfolio/liquidez/` (entradas + retiros) · `/portfolio/liquidez/retirar/` ·
`/alerts/` · `/admin/`
