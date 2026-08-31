# Cómo correr el proyecto

Proyecto Django **PortfolioAR**. Requiere Python 3.8+ y un entorno virtual con las dependencias de `portfolioar/requirements.txt`.

## Prerrequisitos

- Python 3.8+ (en este equipo: 3.12 vía pyenv).
- Entorno virtual con Django instalado. No está instalado en el venv actual (`cs-sgv`), hay que agregarlo.
- Base de datos: por defecto **SQLite** (`USE_SQLITE=True`). No se necesita SQL Server.

## Pasos

Desde la carpeta `portfolioar/` (donde vive `manage.py`):

1. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

   > El venv activo (`cs-sgv`, seteado por `.python-version` en la raíz del repo) ya tiene langchain, openai, pandas, yfinance, pero **no Django**. Este paso lo instala.

2. **Configurar variables de entorno**

   Ya existe `.env` con `USE_SQLITE=True`. Si no existiera, copiar:

   ```bash
   cp .env.example .env
   ```

   Editar según sea necesario:
   - `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=True`, `DJANGO_ALLOWED_HOSTS`.
   - `IOL_USER` / `IOL_PASSWORD`: credenciales de InvertirOnline (opcionales para correr, necesarias para precios reales).
     - **Nota:** si la cuenta IOL tiene 2FA activo, el flujo OAuth2 password de la API puede rechazar el login.
   - `OPENAI_API_KEY`: aún sin uso (RF11 no implementado).

3. **Crear la base de datos**

   ```bash
   python manage.py migrate
   ```

4. **Cargar catálogo** (sectores, brokers, tickers)

   ```bash
   python manage.py loaddata initial_data
   ```

   > Los indicadores técnicos (RSI, MACD, etc.) **no** tienen seed — crear desde `/admin/` (ver GAPS.md).

5. **Crear usuario admin** (para `/admin/`)

   ```bash
   python manage.py createsuperuser
   ```

   Usuarios normales se registran desde la app (`/auth/register/`).

6. **Correr el servidor**

   ```bash
   python manage.py runserver
   # o, equivalente:
   python app.py
   ```

   Navegar a `http://127.0.0.1:8000/` (admin en `/admin/`).

## Tests

```bash
pytest
```

- Usa `portfolioar.settings_test` (SQLite en memoria, `pytest.ini`).
- No requiere `.env` ni base de datos real.

## Notas

- Sin credenciales IOL, las vistas que piden precio actual (`dashboard`, `position_detail`, `/portfolio/api/precio/`) fallan o degradan al precio de compra.
- Los endpoints de precios llaman a la API real de IOL (read-only) y a `dolarapi.com`; requieren internet.
- SQL Server solo se usa si `USE_SQLITE=False` (no configurado en este entorno).