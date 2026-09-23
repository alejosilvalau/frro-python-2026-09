# Plan de cierre de Casos de Uso (CU01–CU04)

**Audiencia: este plan lo ejecuta otro agente de IA, sin el contexto de la conversación en la
que se escribió.** No asumas nada que no esté explícito acá. Cada fase lista archivos
concretos, qué cambiar y cómo verificarlo. Las decisiones de diseño ya fueron discutidas y
aprobadas por el usuario — no las vuelvas a cuestionar salvo que encuentres un hecho del código
que las contradiga (en ese caso, para y consultá antes de seguir).

## Estado a esta fecha — leer esto primero

Este plan ya se ejecutó en gran parte en el commit `7d627dc` ("feat(portfolio): cerrar flujos
de inversión y alertas"). Antes de tocar nada, correr `git log --oneline -3` y `git show
--stat 7d627dc` para confirmar que ese commit sigue siendo la punta de la rama y ver qué tocó.
Si ya está aplicado (que es lo esperado), lo siguiente **ya está hecho y no hay que repetirlo**:

- Fase 1 completa: `transaction.atomic()` + `select_for_update()` en `add_position`, `add_lot`,
  `add_sale`, `remove_position`, `remove_lot`; parseo con `Decimal` en las vistas (sin `float()`
  intermedio); validación de fecha (`_validate_operation_datetime`/`_parse_operation_datetime`,
  no futura, venta no anterior a la compra que consume); `CheckConstraint` positivos en `Lot` y
  `Sale` (migración `0006_enforce_positive_trade_values.py`).
- Fase 2, resuelto: precio único derivado por CCL para **compras** (`_resolve_lot_prices` en
  `portfolio/business.py`, usado por `add_position`/`add_lot`; formularios `position_form.html`/
  `lot_form.html` con un solo campo de precio); `profit_loss_percentage_usd` para la comparación
  contra S&P500 (usa `avg_cost_usd` + CCL actual); fecha ponderada por monto invertido
  (`fifo.compute_weighted_purchase_date`/`compute_weighted_consumed_purchase_date`/
  `compute_weighted_sale_date`); estados `None`/"no disponible" propagados hasta
  `position_detail.html`; fórmula de Fisher para `real_return`; CAGR para `annualized_return`;
  comparación de posiciones cerradas contra el rendimiento realizado
  (`calculate_position_performance`, rama `open_amount == 0`); `get_indec_inflation_series`
  movido a `data_access.py`.
- Fase 3, resuelto: `alert_update` persiste `stock_id`; `alert_delete`/`alert_remove_condition`
  ahora son POST con CSRF (`@require_POST` + `<form>` en los templates); `RN05` reforzado con
  `choices` + `CheckConstraint` en `AlertCondition` (migración
  `0003_enforce_alert_condition_operator.py`); UI de creación de condiciones
  (`condition_create`, `condition_form.html`); cooldown/deduplicación de disparos con
  `select_for_update` en `create_trigger_if_cooldown_elapsed` (15 minutos, ver
  `alerts/business.py` `ALERT_COOLDOWN`).
- `GAPS.md` y `PROYECTO.md` ya fueron actualizados a mano (sin commitear todavía) para reflejar
  RF10 implementado, el catálogo de indicadores seedeado, y CU04 documentado.
- La suite de tests (145 tests) pasa completa: `DJANGO_SETTINGS_MODULE=portfolioar.settings_test
  python -m pytest -q` desde `TPI/portfolioar/`.

**Lo que falta es específicamente lo que lista la Fase 0 de abajo** — son 3 gaps concretos que
sobrevivieron a esa implementación, verificados leyendo el código real (no son hipótesis de la
auditoría original). Empezar por ahí. Las Fases 1-4 de este documento quedan como referencia
histórica de lo ya resuelto; no hay que re-ejecutarlas.

## Fase 0 — Correcciones pendientes verificadas (hacer esto primero)

### 0.1 — CU04 (venta) no tiene el mismo resguardo de consistencia ARS/USD que CU01 (compra)

**Por qué importa**: es el mismo riesgo que motivó el fix de `_resolve_lot_prices` en compras,
pero solo se cerró la mitad del problema. Hoy `SaleManager.add_sale` (`portfolio/business.py`)
sigue recibiendo `price_local` y `price_usd` como dos valores independientes que el usuario
tipea en `sale_form.html` (dos `<input>` separados, sin relación forzada vía CCL). Un precio
USD arbitrario en una venta contamina directamente `Sale.realized_pnl_usd`, que alimenta
`profit_loss_percentage_usd` y la comparación contra S&P500 de posiciones cerradas — exactamente
la métrica que se pidió cuidar en este cierre.

**Qué hacer**:

1. En `portfolio/business.py`, cambiar la firma de `SaleManager.add_sale` de
   `(self, position_id, amount, price_local, price_usd, sold_at, sell_currency='ARS')` a
   `(self, position_id, amount, price, sold_at, sell_currency='ARS')`, y usar
   `_resolve_lot_prices(price, sell_currency)` (la función ya existe, es genérica — no hace
   falta duplicarla) para obtener `price_local, price_usd` igual que en `add_lot`/`add_position`.
   Mantener el resto de la lógica FIFO/atomicidad sin cambios.
2. En `portfolio/views.py`, `sale_create`: reemplazar el parseo de `price_local`/`price_usd`
   por un único `price = _parse_decimal(request.POST.get('price'), 'El precio')`, y pasar
   `price` (no dos precios) a `sale_manager.add_sale`.
3. En `templates/portfolio/sale_form.html`: aplicar el mismo cambio que ya se hizo en
   `lot_form.html`/`position_form.html` — un solo campo `price` con label dinámico según
   `sell_currency`, y el mismo texto de ayuda sobre que el CCL usado es el del momento de carga.
   Ajustar el JS (`updateProceedsDisplay`, etc.) igual que se hizo en esos otros dos templates.
4. Revisar `portfolio/tests.py`: todos los `sale_manager.add_sale(...)`/
   `SaleManager().add_sale(...)` que hoy pasan `price_local, price_usd` por separado (buscar en
   `SaleFIFOTest`, `SaleViewTest`, y cualquier otro que llame `add_sale`) deben actualizarse a
   la nueva firma de un solo precio, mockeando `get_ccl_rate` donde corresponda (ya está
   parcheado a nivel de clase en `PortfolioTestBase`, ver `ccl_patcher` en `setUp`).
5. Agregar al menos un test que verifique que vender en USD deriva `price_local` desde el CCL
   mockeado (análogo a `test_lot_prices_are_derived_from_the_selected_currency`), y otro que
   confirme que `get_ccl_rate` fallando bloquea la venta con un `ValueError` claro (análogo a
   `test_lot_creation_fails_when_ccl_is_unavailable`).

### 0.2 — `compare_with_sp500`/`compare_with_inflation` recalculan el performance por su cuenta

**Por qué importa**: `portfolio/views.py` (`position_detail` y `dashboard`) ya calcula
`performance = portfolio_manager.calculate_position_performance(position)`, pero
`compare_with_sp500`/`compare_with_inflation` (`portfolio/business.py`) **vuelven a llamar**
`self.calculate_position_performance(position)` internamente. Por posición, eso son 3 llamadas
independientes a `calculate_position_performance` (cada una potencialmente golpeando IOL y CCL)
por cada carga de `position_detail`, multiplicado por posición en `dashboard`. Dos problemas:
rendimiento (un dashboard con varias posiciones dispara decenas de requests externos evitables),
y consistencia (si una de las tres llamadas falla por un timeout transitorio y las otras no,
la misma página puede mostrar tarjetas con números que no cuadran entre sí para la misma
posición, o un valor en una tarjeta y "No disponible" en otra).

**Qué hacer**:

1. Cambiar las firmas en `portfolio/business.py`: `compare_with_sp500(self, position,
   performance=None)` y `compare_with_inflation(self, position, performance=None)`. Si
   `performance` es `None`, calcularlo igual que hoy (mantiene compatibilidad con cualquier otro
   caller que no lo pase). Si se pasa, usarlo directamente sin recalcular.
2. En `portfolio/views.py`, `position_detail` y `dashboard`: calcular `performance` una sola vez
   por posición y pasarlo a ambas comparaciones:
   `portfolio_manager.compare_with_sp500(position, performance)` /
   `portfolio_manager.compare_with_inflation(position, performance)`.
3. Revisar `portfolio/tests.py` por tests que mockeen `calculate_position_performance` y cuenten
   cuántas veces se llama (si existen) — deberían pasar a esperar 1 llamada en vez de 3. Si no
   existen, está bien agregar uno que lo verifique explícitamente (`assert_called_once` sobre
   un mock de `calculate_position_performance`, llamando a `position_detail` vía `Client`).

### 0.3 — Los umbrales de condición de alerta no pueden ser negativos, y ahora hay una UI que lo expone

**Por qué importa**: `ConditionManager.create` (`alerts/business.py`) rechaza
`threshold_value < 0`, y `templates/alerts/condition_form.html` tiene `min="0"` en el input —
el bloqueo es end-to-end. RN05 (`PROYECTO.md`) solo exige operadores válidos, no umbrales no
negativos — esa restricción no tiene respaldo en ningún requisito. El indicador MACD (ya
seedeado por `seed_technical_indicators`) puede ser legítimamente negativo, así que una
condición como "MACD < -1" es imposible de crear desde la aplicación.

**Qué hacer**:

1. En `alerts/business.py`, `ConditionManager.create`: quitar la validación
   `if threshold_value < 0: raise ValueError(...)`.
2. En `templates/alerts/condition_form.html`: quitar `min="0"` del input `threshold_value`.
3. Revisar `alerts/tests.py` por un test que hoy espere que un umbral negativo falle (buscar
   algo como `test_create_negative_threshold_raises` en `ConditionManagerTest`) — hay que
   eliminarlo o invertirlo para que verifique que un umbral negativo **se acepta**.
4. Agregar un test de que una condición "MACD < -1" se puede crear y evaluar correctamente
   (`AlertManagerTest`/`ConditionManagerTest`).

## Contexto

`TPI/AUDITORIA_CASOS_DE_USO.md` es un análisis crítico línea por línea de los 4 casos de uso
documentados en `TPI/PROYECTO.md` (CU01 compra, CU02 rendimiento, CU03 alertas, CU04 venta).
Concluye que ninguno de los 4 puede darse por cerrado tal cual está: hay bugs de integridad
(operaciones no atómicas, condiciones de carrera), bugs funcionales (`alert_update` no guarda
el instrumento, no se pueden crear condiciones desde la UI) y errores conceptuales de cálculo
financiero (fórmulas de rendimiento real y anualizado incorrectas, comparación contra S&P500
mezclando ARS con USD, fallos de API que se disfrazan de resultados reales en vez de mostrarse
como "no disponible").

Leé `TPI/AUDITORIA_CASOS_DE_USO.md` completo antes de tocar código — cada hallazgo ahí tiene
archivo y línea. Este plan no repite el detalle de cada bug, organiza el orden y las decisiones
de cómo resolverlos.

**No hacer commit de estos cambios salvo que el usuario lo pida explícitamente.** Cuando lo
pida, dividir en commits chicos y lógicos (uno por fase o sub-tema), nunca `git add -A`, nunca
`--amend`, sin atribución de IA como coautor salvo que el usuario indique lo contrario.

## Decisiones de diseño ya resueltas

Estas son las respuestas que dio el usuario durante la planificación. No re-preguntar por ellas.

1. **Comparación contra S&P 500 (corrige mezcla de monedas)**: valuar la posición **en USD**
   usando `avg_cost_usd` (ya calculado por `fifo.compute_weighted_avg_cost`) como costo, y el
   precio actual convertido a USD mediante el CCL **actual** (`get_ccl_rate()`, ya existe, no
   agregar una fuente de CCL histórico). Se descartó explícitamente la alternativa de convertir
   el S&P500 a ARS con CCL histórico, porque requeriría una integración externa nueva que no
   existe hoy (`dolarapi.com` solo da el valor actual, no series).

2. **Integridad del precio USD por lote (CU01)**: el usuario identificó que la comparación en
   USD del punto 1 solo es confiable si `Lot.price_usd` refleja de verdad `price_local / CCL`,
   y hoy no lo garantiza — son dos campos numéricos independientes que el usuario puede editar
   sin que el servidor valide su relación. **Decisión: eliminar la doble carga manual.** El
   formulario de compra (`position_form.html`, `lot_form.html`) debe pedir un único precio, en
   la moneda que el usuario eligió en "Pagar con" (`purchase_currency`), y el servidor calcula
   el precio en la otra moneda usando el CCL vigente **en el momento de la request** (no un CCL
   histórico — no existe esa fuente, ver punto 1). Documentar esta limitación explícitamente en
   el propio formulario (texto de ayuda) para compras que se cargan con fecha retroactiva: el
   precio en la moneda no elegida se calcula con el CCL del momento de carga, no con el CCL real
   de `purchased_at`.

3. **Posiciones cerradas en las comparaciones**: cuando `open_amount == 0` (posición cerrada,
   sin lotes abiertos), la comparación contra S&P500/inflación debe hacerse igual, pero usando
   el **rendimiento realizado total** (de las ventas) sobre el período real de esa posición
   (fecha ponderada de compra → fecha ponderada de venta), no comparar un 0% ficticio contra el
   mercado como hace hoy.

4. **Fallos de API externas**: deben propagarse como estado explícito de "no disponible" hasta
   la vista y el template (`position_detail.html`), nunca como `Decimal('0')` ni como un
   fallback silencioso que se vea igual a un dato real. Aplica a: precio actual de IOL,
   inflación INDEC, retorno del S&P500.

5. **Período de comparación con múltiples lotes**: usar una **fecha de apertura ponderada por
   monto invertido de cada lote** en vez de `Position.opened_at` (que hoy es la fecha del
   primer lote, sin importar cuánto pesa cada compra posterior). Esto reemplaza el uso de
   `opened_at` para: `days_held`/`annualized_return`, y como fecha de inicio para las
   comparaciones de S&P500/inflación. **No** implementar XIRR/TWR — queda fuera de alcance.

Además, quedan confirmadas (por ser correcciones directas de fórmula, sin alternativa
razonable) dos correcciones que ya estaban en la auditoría:

6. **Rendimiento real (vs. inflación)**: cambiar `nominal - inflación` por la fórmula de Fisher:
   `real = (1 + nominal/100) / (1 + inflación/100) - 1`, expresado como porcentaje.
7. **Rendimiento anualizado**: cambiar la división simple (`% / años`) por CAGR:
   `((valor_final / valor_inicial) ** (1/años) - 1) * 100`, usando `valor_inicial =
   invested_amount` y `valor_final = current_value` (o los equivalentes realizados para
   posiciones cerradas del punto 3).

## Fuera de alcance (no implementar en este plan)

- CCL histórico / cualquier nueva integración externa para tipo de cambio pasado.
- XIRR/TWR o cualquier retorno ponderado por múltiples flujos de caja.
- Prorrateo de comisiones (`Lot.fees`) en el costo o el P&L — sigue siendo informativo.
- Reescribir el motor de indicadores técnicos o el mapeo de tickers por mercado (mencionado en
  la auditoría de CU02/CU03 como brecha "Media", no bloquea el cierre de los CU).
- Cambiar `CashTransaction.tipo='recupero'` a tipos más granulares — mencionado como brecha
  transversal, no es parte de este cierre.

Si en el camino aparece la tentación de "ya que estamos, arreglemos esto también", no lo hagas
sin confirmar con el usuario — el alcance de este plan es exactamente lo que está escrito acá.

## Fase 1 — Integridad transaccional de CU01 y CU04 (prioridad más alta)

Basado en la sección "Criterio para considerarlo cerrado" de CU01 y CU04 en la auditoría.

1. **Atomicidad.** En `portfolio/business.py`, envolver en `django.db.transaction.atomic()`:
   - `PortfolioManager.add_position` (crea `Position` + `Lot` + `CashTransaction`).
   - `LotManager.add_lot` (crea `Lot` + `CashTransaction` + `sync_position_status`).
   - `SaleManager.add_sale` (crea `Sale` + N `SaleLot` + `CashTransaction` +
     `sync_position_status`).
   - `PortfolioManager.remove_position` y `LotManager.remove_lot` (borrado + reembolsos).
   Verificar que la capa de datos (`data_access.py`) no abra transacciones propias que
   entren en conflicto.

2. **Concurrencia (CU04, crítico).** En `SaleManager.add_sale`, bloquear la posición y sus
   lotes antes de calcular el remanente disponible, usando `select_for_update()` dentro del
   mismo `atomic()` del punto anterior, para que dos ventas simultáneas no puedan leer el mismo
   remanente y sobrevender. Aplicar el mismo criterio a `LotManager.add_lot` /
   `PortfolioManager.add_position` frente a la verificación de liquidez (`CashManager.get_available`)
   para evitar el mismo problema con dos compras simultáneas.

3. **Validación de request con `Decimal`, sin pasar por `float`.** En `portfolio/views.py`,
   los `int()`/`float()` de `position_create`, `lot_create` y `sale_create` se ejecutan antes
   del bloque `try/except ValueError` de negocio, así que un valor malformado (`amount=abc`,
   vacío, `inf`, `nan`) produce un 500 en vez de un error de formulario. Cambiar a: parsear
   con `Decimal(request.POST.get(...))` dentro de un único `try/except (ValueError,
   InvalidOperation, TypeError)` que devuelva el mismo render de error que ya usan las
   validaciones de negocio. No usar `float()` como paso intermedio para precios/montos en
   ningún punto del flujo de compra/venta.

4. **Validación de fecha.** `purchased_at` (compra) y `sold_at` (venta) deben validarse como
   fecha real, no vacía, no en el futuro. Para `sold_at`, además, no debe ser anterior a
   `purchased_at` del lote más antiguo que la venta va a consumir (evita romper la cronología
   FIFO, hallazgo "Alta" de CU04). Si la fecha es inválida, mismo patrón de error de formulario
   que el resto de las validaciones de negocio (no dejar que reviente como excepción no
   controlada).

5. **Constraints de modelo.** Agregar `CheckConstraint` en `Lot` y `Sale` (migración nueva) para
   `amount > 0`, `price_local > 0`, `price_usd > 0`, de forma que la integridad no dependa
   solo de que todo el código pase por los managers.

### Verificación Fase 1

- Tests nuevos: fallo simulado a mitad de `add_sale`/`add_position` (mockear una excepción en
  la segunda escritura) y verificar que no queda nada a medio crear (rollback completo).
- Test de concurrencia: dos llamadas a `add_sale` para la misma posición con cantidad que
  individualmente entra pero sumada no, verificar que la segunda falla con `ValueError` en vez
  de sobrevender (se puede simular con dos threads o, más simple, verificando que el
  `select_for_update` está en el query — un test de integración real de race condition es
  opcional si el tiempo no alcanza, pero como mínimo debe haber un test que reproduzca el
  cálculo secuencial correcto tras el fix).
- `python manage.py test` / `pytest -q` completo en verde.

## Fase 2 — Exactitud de CU02 (rendimiento, S&P500, inflación) — foco principal de este plan

Todo esto vive en `portfolio/business.py` (`PortfolioManager`, `ExternalAPIs`) y
`portfolio/data_access.py`, con impacto en `templates/portfolio/position_detail.html`.

### 2.1 Precio USD consistente por lote (habilita todo lo demás)

- **Formulario** (`templates/portfolio/position_form.html`, `templates/portfolio/lot_form.html`):
  quitar el segundo `<input>` de precio. Dejar un único campo de precio, y actualizar el label
  dinámicamente según la moneda elegida en "Pagar con" (ya hay JS que escucha el cambio de
  `purchase_currency`, extenderlo para mostrar/ocultar el label en vez de dos inputs). Agregar
  un texto de ayuda: "el precio en la otra moneda se calcula automáticamente con el tipo de
  cambio CCL del momento de carga".
- **Vista** (`portfolio/views.py`, `position_create` y `lot_create`): recibir un solo
  `price` + `purchase_currency`. Ya no recibir `price_local`/`price_usd` del POST.
- **Negocio** (`portfolio/business.py`, `PortfolioManager.add_position` y `LotManager.add_lot`):
  agregar un paso que, dado `price` y `purchase_currency`, obtenga `ccl = get_ccl_rate()` (ya
  existe en `data_access.py`) y calcule:
  - si `purchase_currency == 'ARS'`: `price_local = price`, `price_usd = price / ccl`.
  - si `purchase_currency == 'USD'`: `price_usd = price`, `price_local = price * ccl`.
  Envolver la llamada a `get_ccl_rate()` en manejo de error: si el servicio de CCL falla, no se
  puede completar la compra de forma consistente — devolver `ValueError` claro ("No se pudo
  obtener el tipo de cambio para validar el precio, intentá de nuevo") en vez de guardar un
  precio sin su contraparte.
- Actualizar `portfolio/tests.py` en todos los `PortfolioManager().add_position(...)` /
  `LotManager().add_lot(...)` de los tests existentes que hoy pasan `price_local` y
  `price_usd` por separado — van a necesitar mockear `get_ccl_rate` y pasar la nueva firma.
  Revisar cuidadosamente `PortfolioTestBase`, `LotModelTest`, `SaleFIFOTest`,
  `PositionCreateViewTest`, `LotViewsTest` en `portfolio/tests.py`.

### 2.2 Rendimiento en USD para la comparación contra S&P500

En `PortfolioManager.calculate_position_performance` (o una función nueva dedicada, ej.
`calculate_position_performance_usd`, para no romper el contrato ARS que ya consumen
`position_detail.html`/`dashboard.html`):

```
invested_amount_usd = avg_cost_usd * open_amount
current_price_usd = current_price_ars / ccl_actual   # None si falta cualquiera de los dos
current_value_usd = current_price_usd * open_amount  # None si current_price_usd es None
profit_loss_percentage_usd = (current_value_usd - invested_amount_usd) / invested_amount_usd * 100
```

`compare_with_sp500` debe usar `profit_loss_percentage_usd` (no el `profit_loss_percentage`
en ARS actual) para calcular `alpha = profit_loss_percentage_usd - sp500_return`. Si
`current_price_usd` es `None` (falta precio de IOL o falta CCL), `alpha` debe ser `None`
— ver 2.4.

### 2.3 Fecha ponderada por monto invertido (multi-lote)

Nueva función en `portfolio/fifo.py` (es cálculo puro sobre lotes, no ORM, así que va ahí junto
al resto de las funciones FIFO):

```python
def compute_weighted_purchase_date(open_lots):
    """open_lots: [(lot, remaining_amount)]. Devuelve la fecha ponderada por
    remaining_amount * price_local de cada lote, o None si no hay lotes abiertos."""
```

Usarla en `calculate_position_performance` en vez de `position.opened_at` para:
`days_held`/`years_held` (y por lo tanto el nuevo cálculo de CAGR del punto 6 de las
decisiones), y como fecha de inicio en `compare_with_sp500`/`compare_with_inflation`.

Para posiciones cerradas (Fase 2.5) hace falta el equivalente para lotes consumidos por venta
(ponderar por `SaleLot.amount_consumed * cost_price_local`) y una fecha ponderada de venta
(ponderar por `Sale.amount * Sale.price_local` sobre las ventas de esa posición). Se puede
implementar como una segunda función `compute_weighted_sale_date` en el mismo módulo, o
generalizar una sola función que reciba pares `(fecha, peso)` — preferir esta segunda opción
para no duplicar la lógica de promedio ponderado.

### 2.4 Estados "no disponible" en vez de ceros

- `ExternalAPIs.get_indec_inflation`: que devuelva `None` (no `Decimal('0')`) si la respuesta
  no tiene al menos 2 observaciones, si el status no es 200, o ante cualquier excepción.
- `ExternalAPIs.get_sp500_performance`: mismo criterio, `None` en vez de `Decimal('0')`.
- `ExternalAPIs.get_current_price`: ya devuelve `None` en el fallo — no cambiar, pero revisar
  que nadie más abajo lo reemplace silenciosamente por `avg_cost_local` como hace hoy
  `calculate_position_performance` (esa sustitución es precisamente el hallazgo "Crítica" de
  CU02 — hay que sacarla).
- `calculate_position_performance`: si `current_price` es `None`, todo lo que depende de él
  (`current_value`, `profit_loss`, `profit_loss_percentage`, `annualized_return`,
  `profit_loss_percentage_usd`) debe ser `None`, no un valor calculado con el costo como
  sustituto. Agregar una key explícita, ej. `price_unavailable: True`.
- `compare_with_sp500`/`compare_with_inflation`: si cualquiera de los dos operandos de la
  resta/fórmula es `None`, el resultado (`alpha`, `real_return`) debe ser `None`.
- **Vista y template**: `position_detail` (`portfolio/views.py`) sigue pasando el dict de
  performance tal cual; `templates/portfolio/position_detail.html` debe chequear cada campo
  (`{% if performance.current_value is None %}No disponible{% else %}...{% endif %}` o
  equivalente) en vez de asumir que siempre hay un número. Aplica a las cards de P&L no
  realizado, alpha vs S&P500, y rendimiento real vs inflación.
- Actualizar el test `test_indec_failure_is_handled_gracefully` en `portfolio/tests.py`
  (`PositionDetailViewTest`) — hoy ese test probablemente valida el comportamiento viejo
  (0% silencioso); ajustarlo para que verifique que se muestra el estado "no disponible".

### 2.5 Posiciones cerradas: comparar contra el rendimiento realizado

En `calculate_position_performance`, cuando `open_amount == 0` y la posición tiene al menos
una venta:
- Calcular `total_cost_of_sold_lots` = suma de `SaleLot.amount_consumed * SaleLot.cost_price_local`
  (y el equivalente en USD con `cost_price_usd`) sobre todas las `SaleLot` de la posición.
- `realized_return_percentage = realized_pnl_ars / total_cost_of_sold_lots * 100`.
- Período: `compute_weighted_purchase_date` de los lotes vendidos → `compute_weighted_sale_date`
  de las ventas (ver 2.3).
- `compare_with_sp500`/`compare_with_inflation` deben usar este `realized_return_percentage` y
  este período (en vez de `profit_loss_percentage`/`opened_at`) cuando la posición está
  cerrada. Si la posición está abierta (`open_amount > 0`), seguir usando el flujo no
  realizado como hasta ahora — no se pide (ni se intente) mezclar tramos realizados y no
  realizados de una misma posición en una sola comparación; eso es exactamente el problema de
  flujos múltiples que quedó fuera de alcance (XIRR/TWR).

### 2.6 Fórmulas (decisiones 6 y 7)

- `real_return`: reemplazar la resta por la fórmula de Fisher (decisión 6). Igual criterio de
  "no disponible" si `inflation` es `None`.
- `annualized_return`: reemplazar por CAGR (decisión 7), usando `invested_amount`/
  `current_value` (o los equivalentes realizados de 2.5 para posiciones cerradas). Si
  `years_held` es 0 (posición abierta hoy mismo), devolver `None` en vez de dividir por cero
  (revisar que hoy no rompa; actualmente hay un chequeo `if years_held > 0 else Decimal('0')`
  que hay que ajustar al nuevo criterio de "no disponible").

### 2.7 Arquitectura

`ExternalAPIs.get_indec_inflation` usa `requests` directamente en `business.py`
(`portfolio/business.py`), violando la separación de capas (`checklist_capas.md`: la capa de
negocio no debe hacer I/O externo directo, eso es de `data_access.py`). Mover la llamada HTTP
a una función nueva en `portfolio/data_access.py` (ej. `get_indec_inflation_series(start_date,
end_date)` que devuelve la serie cruda o `None`), y dejar en `business.py` solo el cálculo
sobre esos datos.

### Verificación Fase 2

- Tests unitarios de las nuevas funciones puras en `fifo.py` (`compute_weighted_purchase_date`,
  fecha ponderada de venta) con casos de 1 lote, 2 lotes de igual peso, 2 lotes de peso
  distinto.
- Tests de `calculate_position_performance`/`compare_with_sp500`/`compare_with_inflation`
  mockeando `get_ccl_rate`, `get_current_price`, `get_sp500_performance`,
  `get_indec_inflation` para cubrir: caso normal, CCL no disponible, IOL no disponible, INDEC
  no disponible, SP500 no disponible, posición cerrada con ventas, posición con lotes en
  fechas muy distintas (verificar que el período ponderado no es igual a `opened_at` cuando
  los pesos son distintos).
- Test de vista de `position_detail` verificando que el HTML muestra "No disponible" (o el
  texto que se elija) cuando cualquiera de las fuentes externas falla, no un `0%`.
- Recalcular a mano (fuera del código, en la descripción del test) al menos un caso de alpha en
  USD y un caso de rendimiento real con Fisher, para verificar que el número que devuelve el
  código coincide con la cuenta manual.

## Fase 3 — Usabilidad de CU03 (alertas)

Basado en la sección de CU03 de la auditoría. Menor prioridad que Fases 1-2 porque no involucra
errores de cálculo financiero, pero sin esto CU03 no es utilizable de punta a punta en una
instalación nueva.

1. **Crear condiciones desde la UI.** Agregar vista+template para crear `AlertCondition`
   (indicador, operador, umbral), reutilizando `ConditionManager.create` (que ya valida RN05).
   Alternativa más chica si no se quiere UI nueva: sembrar un catálogo inicial de condiciones
   "aceptado por el equipo" vía `seed_technical_indicators` o un seed nuevo — pero esto no
   reemplaza la necesidad de poder crear condiciones custom, solo destraba el arranque en frío.
   Definir con el usuario cuál de las dos alcanza para este cierre si el tiempo no permite
   ambas.
2. **`alert_update` debe persistir `stock_id`.** En `alerts/views.py`, agregar el campo al
   `update_alert` de negocio y al POST de la vista.
3. **Acciones destructivas por POST.** `alert_delete` y `alert_remove_condition`
   (`alerts/urls.py`, `alerts/views.py`, `templates/alerts/alert_detail.html`,
   `templates/alerts/alert_list.html`) deben aceptar solo `POST` (usar `<form>` con
   `{% csrf_token %}` en vez de `<a href>`, y `@require_POST` en la vista).
4. **RN05 también en el modelo.** Agregar `choices` al campo operador de `AlertCondition`
   para que una escritura directa (admin, fixture) no pueda saltarse los operadores válidos.
5. **Deduplicación de disparos.** En `evaluate_alerts`/`AlertManager.evaluate_alert`, no crear
   un `AlertTrigger` si ya existe uno para la misma alerta sin que la condición haya pasado por
   un ciclo falso→verdadero (o, más simple para este alcance: no duplicar si el último trigger
   de esa alerta fue hace menos de X minutos — definir X con el usuario, por ejemplo el mismo
   intervalo del cron documentado).

### Verificación Fase 3

- Test de que crear/editar una alerta persiste el instrumento elegido.
- Test de que `alert_delete`/`alert_remove_condition` rechazan GET (405) y aceptan POST.
- Test de que un operador inválido no puede guardarse ni siquiera vía `AlertCondition.objects.create(...)` directo (constraint o `choices` a nivel de base, no solo en el manager).
- Test de que evaluar la misma alerta dos veces seguidas con la condición sostenida no duplica
  el `AlertTrigger`.

## Fase 4 — Limpieza transversal

- ~~Separar `CashTransaction.tipo` en algo más granular que `compra`/`recupero`~~ — **ya
  resuelto** en `7d627dc`: ahora son `compra`/`venta`/`reembolso` (migración
  `0007_separate_cash_transaction_types.py`, con `CheckConstraint` a nivel de base). No repetir.
- Revisar que ningún test quedó dependiendo de red real tras estos cambios. Ya está bien
  resuelto para los tests nuevos (`get_ccl_rate` mockeado a nivel de clase en
  `PortfolioTestBase`), pero confirmar puntualmente si `PortfolioManagerTest`/`SaleFIFOTest`
  todavía tienen algún método sin mockear que golpee red real (yfinance/IOL/INDEC) — si aparece
  alguno al tocar Fase 0, mockearlo ahí mismo en vez de dejarlo para después.

## Orden de ejecución sugerido

1. **Fase 0 (correcciones pendientes verificadas)** — hacerla primero y completa. Es chica,
   tiene alcance acotado y es la que más impacta la corrección de P&L/comparaciones, que es la
   prioridad del usuario.
2. Fase 4, ítem de tests con red real, si aparece algo al tocar Fase 0.
3. Fases 1-3 y el resto de Fase 4: **no ejecutar**, ya están hechas por `7d627dc` (ver
   "Estado a esta fecha" al principio del documento). Solo volver a ellas si al revisar el
   código encontrás que alguna parte descripta ahí en realidad no está aplicada — en ese caso
   parar y avisar antes de asumir que hay que reconstruirla desde cero.

Después de Fase 0: correr `DJANGO_SETTINGS_MODULE=portfolioar.settings_test python -m
pytest -q` completo desde `TPI/portfolioar/` y confirmar verde (hoy son 145 tests; van a ser
más una vez agregados los de 0.1/0.2/0.3).

## Actualización de documentación al cerrar

Cuando la Fase 0 esté terminada y verificada (tests en verde):

- Actualizar `TPI/AUDITORIA_CASOS_DE_USO.md`: está desactualizado, describe el estado *antes*
  de `7d627dc` (dice que no hay atomicidad, que S&P500 mezcla monedas, etc. — ya no es así).
  Hacer una pasada completa marcando qué se cerró en `7d627dc` y agregar los 3 hallazgos de la
  Fase 0 como brechas nuevas de CU04/CU02/CU03 hasta que se resuelvan; una vez resueltas,
  marcarlas también.
- Actualizar `TPI/GAPS.md`: hoy dice "no quedan requerimientos ni casos de uso pendientes de
  implementación" — eso es sobre-optimista mientras existan los gaps 0.1/0.2/0.3. No dejar esa
  afirmación mientras haya algo pendiente; ajustarla recién cuando la Fase 0 esté cerrada.
- Si Fase 0.1 cambia la firma de `add_sale`, o si Fase 0.2 cambia la firma de
  `compare_with_sp500`/`compare_with_inflation`, actualizar `TPI/HANDOFF_IA.md` en la sección
  "Mapa rápido de archivos clave" si el comportamiento descrito ahí quedó desactualizado.
