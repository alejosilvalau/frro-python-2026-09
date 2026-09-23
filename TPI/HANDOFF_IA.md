# Handoff para asistente de IA — PortfolioAR

Este documento es para otro asistente de IA (no Claude) que retome este proyecto sin el
historial de conversación previo. No es documentación de producto: es contexto operativo
para poder seguir trabajando sin romper convenciones ya establecidas.

## Qué es el proyecto

TPI universitario (Análisis de Sistemas, FRRO/UTN) llamado **PortfolioAR**: una app Django
para que un inversor argentino registre posiciones de acciones/CEDEARs/bonos, compre y
venda con costeo FIFO, controle liquidez en ARS/USD, compare rendimiento contra S&P 500 e
inflación INDEC, y configure alertas técnicas (RSI, precio, volumen).

Lee `TPI/PROYECTO.md` primero: tiene el modelo de dominio, requerimientos funcionales (RF),
no funcionales (NFR), reglas de negocio (RN01–RN06) y los 4 casos de uso documentados
(CU01–CU04). Lee `TPI/GAPS.md` después: es el análisis vivo de qué falta contra esa
documentación — se actualiza a medida que se implementa o se decide sacar un requisito.

## Stack y arquitectura

- Django 4.2/6.1 (ver `requirements.txt`), SQLite en desarrollo local (`USE_SQLITE=True` en
  `.env`), SQL Server como opción de producción (no usada en desarrollo).
- **Arquitectura estricta de 3 capas por app** (`core`, `portfolio`, `alerts`):
  - `views.py` — HTTP únicamente. No debe llamar directamente al ORM.
  - `business.py` — reglas de negocio, en clases tipo `XManager`. No debe importar Django
    request/response. Es la única capa con lógica no trivial.
  - `data_access.py` — el único archivo que toca el ORM (`Model.objects...`).
  - Esta separación es un requisito explícito de la cátedra (ver `TPI/checklist_capas.md`)
    y se respeta en todo el código. No la rompas al agregar features.
- Tests con `pytest-django`, settings de test en `portfolioar/settings_test.py`. Correr con:
  ```
  DJANGO_SETTINGS_MODULE=portfolioar.settings_test python -m pytest -q
  ```
  149 tests, todos pasando a la fecha de este documento (hace llamadas mockeadas a
  APIs externas en los tests nuevos; algunos tests viejos de `PortfolioManagerTest` y
  `SaleFIFOTest` todavía golpean red real — ver sección "Deuda técnica conocida").

## Estado actual (resumen de lo recién hecho)

Se completó un refactor grande: el modelo de posiciones pasó de `Position` (con
cantidad/precio propios) + `Order` (compras adicionales sueltas, sin afectar el portfolio)
a un esquema `Position` (contenedor) + `Lot` (compras, FIFO) + `Sale`/`SaleLot` (ventas con
consumo de lotes más antiguos primero). Esto habilitó:

- Compra y venta reales desde la UI (botón "Operar" con dropdown Comprar/Vender), tanto en
  el listado de posiciones como en el detalle.
- P&L realizado (de ventas) separado de P&L no realizado (de lo que sigue abierto).
- Liquidez (`CashPosition` + `CashTransaction`) linkeada a las operaciones: comprar debita,
  vender acredita automáticamente. Los movimientos distinguen compra, venta y reembolso por
  eliminación, para conservar el significado contable. No se puede comprar sin liquidez
  suficiente ni vender más de lo que hay abierto.
- Reglas de borrado: una posición sin ventas se puede borrar (devuelve el cash de todos sus
  lotes); una posición con ventas está bloqueada (protege el historial de P&L realizado). Un
  lote ya consumido por una venta no se puede borrar individualmente.

Los requisitos RF06 (correlación), RF09 (alertas técnicas avanzadas) y RF11 (asistente IA)
se **retiraron formalmente** de `PROYECTO.md` por decisión del equipo — el código que ya
existía para partes de RF06/RF09 se dejó funcionando como extra, no exigido. Se limpiaron
las dependencias de `langchain`/`openai` del `requirements.txt` y `.env.example` que
correspondían a RF11.

Se agregó cobertura de tests de vista (HTTP) para los 4 CU documentados, autenticación
(incluye RN01/RN02) y las nuevas vistas de lote/venta/liquidez — antes de esto la suite solo
tenía tests de modelo/negocio, cero tests de vista en todo el proyecto.

También se completó RF10: `python manage.py evaluate_alerts` procesa las alertas activas,
omite de forma segura las que no tienen condiciones o datos suficientes y registra los
disparos en `AlertTrigger`. Aplica un cooldown persistido de 15 minutos por alerta para no
duplicar notificaciones con una condición sostenida. El comando está pensado para ejecutarse
periódicamente con cron.
El catálogo de indicadores se carga de forma idempotente con
`python manage.py seed_technical_indicators`, comando que también invoca `seed_demo_data`.
CU04 documenta la venta FIFO y la documentación de seguridad refleja el uso real de PBKDF2.

La compra y la venta reciben un único precio en la moneda elegida y calculan la contraparte
ARS/USD con el CCL vigente; si CCL falla, la operación se rechaza. Para evitar repetir I/O y
mezclar instantáneas, `compare_with_sp500(position, performance=None)` y
`compare_with_inflation(position, performance=None)` aceptan el diccionario ya calculado por
`calculate_position_performance`. Las condiciones de alerta aceptan umbrales negativos, por
lo que MACD puede configurarse debajo de cero.

## Deuda técnica conocida (no resuelta, no es urgente salvo que se pida)

1. `PortfolioManagerTest` y parte de `SaleFIFOTest` en `portfolio/tests.py` todavía hacen
   llamadas de red reales (yfinance, IOL, INDEC) en vez de mockearlas como los tests nuevos.
   Los hace lentos y potencialmente flaky. Nadie pidió arreglarlo todavía — no lo toques sin
   que te lo pidan explícitamente.

No quedan gaps funcionales documentados; `TPI/GAPS.md` conserva el estado de cada ítem
cerrado. La mención a snapshots diarios se retiró porque no correspondía a ningún RF ni CU.
Las métricas de posición pueden devolver `None` cuando falla una fuente externa; las vistas
deben mostrar ese estado como “No disponible”, nunca sustituirlo por cero o por costo.

## Cómo correr el proyecto en local

```bash
cd TPI/portfolioar
cp .env.example .env   # si no existe ya; USE_SQLITE=True alcanza para desarrollo
python -m venv .venv && source .venv/bin/activate   # o el venv que ya exista en el repo
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data   # crea usuario demo + liquidez cargada (idempotente)
python manage.py runserver
```

Credenciales del usuario demo tras `seed_demo_data`: `demo@test.com` / `demo1234`, con
liquidez ARS 5.000.000 y USD 5.000 precargada.

No hay `IOL_USER`/`IOL_PASSWORD` real configurado en este entorno de forma segura para vos:
si necesitás probar la integración con IOL, pedile las credenciales al usuario — nunca las
inventes ni las commitees. `DJANGO_ALLOWED_HOSTS` en `.env` no incluye `testserver`; si vas
a hacer pruebas ad-hoc con el `Client` de Django fuera de la suite de tests, puede hacer
falta agregarlo temporalmente sin commitearlo.

## Convenciones de trabajo que el usuario espera

- **No implementar features/fixes no pedidas sin preguntar antes.** El usuario pidió
  explícitamente: "cuando yo sugiera una feature/fix no debes implementarla de inmediato,
  previamente debes preguntarme y planificar la implementación". Para cambios grandes,
  planificar primero y esperar aprobación explícita.
- **No hacer commit salvo que se pida explícitamente.** Cuando se pida, commits chequeados y
  en orden lógico (por capa/tema), nunca con `git add -A` a ciegas, nunca con `--amend`
  salvo pedido explícito.
- **No agregar atribución de IA como coautor** en los commits de este proyecto salvo que el
  sistema/entorno del asistente lo exija de forma no evitable — confirmar con el usuario si
  hay dudas, porque en sesiones previas se pidió explícitamente no hacerlo.
  Nota: la configuración vigente de este handoff puede variar según el proveedor de IA que
  lo use; revisar las instrucciones de sistema del entorno donde se ejecute antes de asumir
  nada al respecto.
- Migraciones de Django: si hace falta renombrar/reestructurar modelos, hacerlo en pasos
  separados (crear modelo nuevo → data migration con `RunPython`/`apps.get_model` → borrar
  lo viejo en una migración posterior) para evitar el prompt interactivo de detección de
  renombrado de Django, y para no forzar a mezclar create+delete en el mismo diff.
- La base SQLite de desarrollo (`db.sqlite3`) está en `.gitignore` — se puede recrear
  libremente con `migrate` + `seed_demo_data` sin preocuparse por perder datos versionados.

## Mapa rápido de archivos clave

- `TPI/PROYECTO.md` — fuente de verdad de requisitos/arquitectura/CU.
- `TPI/GAPS.md` — qué falta vs. esa documentación, mantenido actualizado.
- `portfolio/models.py` — `Position`, `Lot`, `Sale`, `SaleLot`, `CashPosition`,
  `CashTransaction`.
- `portfolio/fifo.py` — funciones puras de costeo FIFO (sin ORM), usadas por
  `SaleManager.add_sale` en `business.py`.
- `portfolio/business.py` — `PortfolioManager`, `LotManager`, `SaleManager`; compra/venta
  resuelven precios por CCL y las comparaciones aceptan un `performance` opcional.
- `core/management/commands/seed_demo_data.py` — seed idempotente de usuario, liquidez e indicadores.
- `alerts/management/commands/evaluate_alerts.py` — ejecución programable de RF10.
- `portfolio/tests.py`, `alerts/tests.py`, `core/tests.py` — suite de tests por capa/app.
