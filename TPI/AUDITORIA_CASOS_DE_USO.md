# Auditoría de casos de uso — PortfolioAR

Fecha de revisión original: 22 de septiembre de 2026.

Actualización de remediación: 23 de septiembre de 2026 (Fases 0–4 de
[`plan.md`](plan.md), verificadas con 149 tests).

## Alcance y criterio

Esta auditoría contrasta los casos de uso CU01–CU04 definidos en
[`PROYECTO.md`](PROYECTO.md) contra la implementación actual en vistas, negocio, acceso a
datos, templates y tests. No evalúa solamente si existe una pantalla: se considera si el
flujo completo produce datos correctos, informa los fallos y preserva la integridad del
sistema.

Estados utilizados:

- **Cumple**: camino básico y alternativo implementados de punta a punta, sin una brecha que
  cambie el resultado del caso de uso.
- **Cumple con reservas**: el comportamiento documentado funciona, pero quedan problemas de
  robustez que pueden producir errores ante entradas o fallos no contemplados.
- **Parcial**: existe el flujo principal, pero una parte esencial es incorrecta, incompleta o
  depende de preparación manual no documentada.
- **No cumple**: el flujo no puede completarse o no produce el resultado declarado.

## Resumen ejecutivo

| Caso de uso | Estado real | Conclusión |
| --- | --- | --- |
| CU01 – Registrar posición de compra | **Cumple** | Compra atómica, validada con `Decimal`, fecha válida y precios ARS/USD consistentes mediante CCL vigente. |
| CU02 – Consultar rendimiento | **Cumple** | Separamos ARS/USD, corregimos CAGR/Fisher, informamos fuentes no disponibles y reutilizamos una única instantánea de performance por posición. |
| CU03 – Configurar alerta técnica | **Cumple con reservas operativas** | El flujo es realizable desde la UI, RN05 se fuerza en base de datos, permite umbrales negativos y los disparos tienen cooldown de 15 minutos; el cron sigue siendo responsabilidad del despliegue. |
| CU04 – Registrar venta FIFO | **Cumple** | Venta FIFO atómica, con bloqueo de posición/lotes, fechas coherentes, constraints y precio único convertido mediante CCL vigente. |

Conclusión general actualizada: los cuatro CU documentados tienen su camino básico y sus
validaciones críticas implementados. Las limitaciones restantes de datos de mercado y
programación del comando se documentan como condiciones operativas, no se presentan como
valores financieros ficticios.

### Remediación aplicada después de la auditoría

El detalle de hallazgos que sigue conserva la fotografía original. Estas correcciones ya se
aplicaron y están cubiertas por pruebas:

| Fase | Brechas cerradas |
| --- | --- |
| 1 — CU01/CU04 | Atomicidad de compra, lote, venta y borrado; bloqueos para saldo y FIFO; parseo seguro; cronología; constraints positivos. |
| 2 — CU02 | Precio único convertido por CCL, rendimiento USD para S&P 500, período ponderado, posiciones cerradas, CAGR, Fisher y estados `No disponible`. |
| 3 — CU03 | Alta de condiciones desde UI, persistencia de instrumento al editar, DELETE/remover por POST+CSRF, constraint de RN05 y cooldown de 15 minutos. |
| 4 — Liquidez | Separamos los créditos de caja por `venta` y por `reembolso` al eliminar posición/lote; la migración clasifica el historial anterior sin perderlo. |
| 0 — Correcciones verificadas | Venta con precio único convertido por CCL, comparaciones reutilizando la misma instantánea de performance y umbrales negativos válidos para MACD. |

No forman parte de este cierre: CCL histórico, XIRR/TWR, prorrateo de comisiones, mapeo de
símbolos por mercado y scheduler gestionado por la propia aplicación.

> Los apartados “Brechas” que siguen son el registro histórico de la revisión original. Cada
> dictamen actualizado documenta qué hallazgos fueron cerrados; no describen el estado actual
> salvo donde se indique expresamente que una limitación sigue fuera de alcance.

---

## CU01 – Registrar posición de compra

### Comportamiento documentado

Un usuario autenticado selecciona instrumento y broker, ingresa cantidad, precio y fecha,
se validan RN03/RN04 y se registra la posición. Si la cantidad o el precio no son positivos,
se informa el error sin guardar.

### Implementación encontrada

1. La vista exige autenticación y obtiene stocks, brokers y liquidez disponible
   ([`portfolio/views.py`](portfolioar/portfolio/views.py)).
2. Convierte los datos recibidos y llama a `PortfolioManager.add_position`.
3. Negocio valida cantidad, ambos precios, moneda y liquidez
   ([`portfolio/business.py`](portfolioar/portfolio/business.py#L90)).
4. Se crean `Position`, `Lot` y `CashTransaction`, debitando la liquidez.
5. Los tests verifican autenticación, creación exitosa, cantidad inválida y liquidez
   insuficiente ([`portfolio/tests.py`](portfolioar/portfolio/tests.py#L231)).

### Qué cumple

- Requiere sesión iniciada.
- Valida cantidad y precios positivos.
- Verifica liquidez antes de comprar.
- Registra un lote y el correspondiente débito de efectivo.
- Redirige al listado tras una compra válida.
- Impide consultar posiciones de otro usuario en el flujo posterior.

### Brechas

#### Alta — La operación no es atómica

La creación de posición, lote y movimiento de efectivo son tres escrituras separadas. Si
falla la segunda o tercera, puede quedar una posición sin lote o una compra sin débito. No
se usa `transaction.atomic` ([`portfolio/business.py`](portfolioar/portfolio/business.py#L109)).

#### Media — Datos malformados producen error 500

La vista ejecuta `int()` y `float()` antes de entrar al bloque que captura `ValueError`.
Entradas como `amount=abc`, valores vacíos manipulados o números no finitos no generan un
error de formulario controlado ([`portfolio/views.py`](portfolioar/portfolio/views.py#L86)).

#### Media — Dinero convertido mediante `float`

Los precios se convierten primero a `float` y después a `Decimal`, introduciendo una etapa
innecesaria de punto flotante. Deberían validarse directamente como `Decimal`.

#### Media — Fecha insuficientemente validada

No se valida que `purchased_at` exista, sea una fecha válida o no esté en el futuro. Tampoco
hay una regla explícita sobre fechas de mercado.

#### Media — Sin restricciones de integridad en base de datos

`Lot.amount` y sus precios no tienen `CheckConstraint`. Las reglas solo se preservan si todas
las escrituras pasan por el manager.

#### Baja — Las comisiones no afectan el costo

El modelo permite `fees`, pero no se suman al débito ni al costo base. En la primera compra
ni siquiera se solicitan desde la pantalla. Esto puede ser una decisión de alcance, pero debe
quedar explícito porque afecta el rendimiento posterior.

### Dictamen

**Dictamen original: cumple con reservas. Dictamen actualizado: cumple.** Atomicidad,
bloqueos de liquidez, parseo con `Decimal`, fechas y constraints positivos quedaron cerrados
en `7d627dc`. Las comisiones siguen explícitamente fuera de alcance.

### Criterio para considerarlo cerrado

- Validar el request con un formulario Django y `Decimal`.
- Ejecutar posición + lote + movimiento de efectivo en una transacción atómica.
- Validar fecha y valores finitos.
- Añadir restricciones positivas en el modelo o justificar por qué se confía solo en negocio.
- Definir formalmente si las comisiones integran el costo.

---

## CU02 – Consultar rendimiento de una posición

### Comportamiento documentado

El sistema obtiene el precio actual, calcula ganancia/pérdida absoluta, porcentual y
anualizada, compara contra S&P 500 e inflación INDEC para el mismo período y presenta los
resultados. Si INDEC falla, debe mostrar un error y omitir esa comparación.

### Cómo se obtienen actualmente los datos

#### Precio actual

Se autentica contra IOL y consulta
`/api/v2/bCBA/Titulos/{ticker}/Cotizacion`, tomando `ultimoPrecio`
([`portfolio/data_access.py`](portfolioar/portfolio/data_access.py#L61)).

#### S&P 500

`yfinance` descarga el símbolo `^GSPC` desde la fecha de apertura hasta hoy. El rendimiento
es `(último cierre / primer cierre - 1) × 100`
([`portfolio/data_access.py`](portfolioar/portfolio/data_access.py#L75)).

#### Inflación INDEC

Se consulta la API de Series de Tiempo de datos.gob.ar con la serie
`148.3_INIVELNAL_DICI_M_26`, usando los meses de apertura y fin. La inflación se calcula como
`(índice final / índice inicial - 1) × 100`
([`portfolio/business.py`](portfolioar/portfolio/business.py#L35)).

### Qué cumple

- La vista de detalle está protegida y verifica pertenencia de la posición.
- Obtiene una cotización actual de IOL cuando hay credenciales y el servicio responde.
- Consulta una serie real del S&P 500 y una serie oficial de precios del INDEC.
- Calcula y muestra P&L realizado/no realizado, comparaciones e indicadores técnicos.
- Hay tests HTTP del camino normal con las APIs simuladas.

### Brechas

#### Crítica — Ante un fallo de IOL se fabrica un rendimiento de 0%

Si no hay cotización, `calculate_position_performance` reemplaza el precio actual por el costo
promedio. La interfaz muestra entonces que la inversión no ganó ni perdió, sin advertir que
el dato no existe ([`portfolio/business.py`](portfolioar/portfolio/business.py#L155)).

#### Alta — Mezcla ARS con USD en la comparación contra S&P 500

El rendimiento de la posición se calcula con costo y cotización local en ARS. `^GSPC` mide el
índice estadounidense en USD. Restarlos como si fueran rendimientos comparables no responde
si el inversor argentino superó al mercado. Se debe elegir una moneda común:

- calcular posición y benchmark en USD; o
- convertir el S&P 500 a ARS usando el tipo de cambio correspondiente a inicio y fin.

#### Alta — El rendimiento real usa una fórmula incorrecta

El código calcula `rendimiento nominal - inflación`
([`portfolio/business.py`](portfolioar/portfolio/business.py#L211)). La fórmula compuesta es:

```text
rendimiento real = (1 + rendimiento nominal) / (1 + inflación) - 1
```

La resta puede servir como aproximación para tasas pequeñas, pero no para inflación argentina.

#### Alta — El rendimiento anualizado no es CAGR

Se divide el porcentaje por la cantidad de años. La fórmula correcta para una inversión sin
flujos intermedios es `(valor_final / valor_inicial)^(1/años) - 1`. Con múltiples compras o
ventas se necesita una métrica que contemple flujos, por ejemplo XIRR o TWR.

#### Alta — El camino alternativo de INDEC no está implementado

Cualquier error, respuesta inválida o falta de dos observaciones se transforma en
`Decimal('0')`. La pantalla muestra “Inflación INDEC: 0%” y calcula un rendimiento real como
si el servicio hubiera respondido. No muestra mensaje ni omite la comparación, en contra de
CU02 ([`portfolio/business.py`](portfolioar/portfolio/business.py#L37)). El test actual
consolida precisamente ese comportamiento incorrecto
([`portfolio/tests.py`](portfolioar/portfolio/tests.py#L317)).

#### Alta — Múltiples lotes no se comparan por sus períodos reales

Se usa el costo promedio de todos los lotes abiertos, pero el período de comparación comienza
en `Position.opened_at`, fecha del primer lote. Una compra posterior queda evaluada como si
hubiera estado invertida desde el inicio.

#### Alta — Las posiciones cerradas generan comparaciones engañosas

Cuando no quedan títulos, el rendimiento no realizado se fija en cero. Luego ese 0% se compara
contra S&P 500 e inflación, aunque la posición tenga P&L realizado.

#### Media — Diferencia entre documentación e instrumento

RF04 menciona S&P 500/SPY, pero se consulta `^GSPC`. El índice y el ETF siguen el mismo mercado,
pero SPY incorpora gastos y distribuciones; debe definirse cuál es el benchmark oficial.

#### Media — Resolución mensual de inflación

La consulta usa meses completos. Una compra a mitad de mes no tiene ajuste prorrateado y una
posición dentro de un único mes puede devolver menos de dos puntos y terminar como 0%.

#### Media — Los indicadores pueden representar otro mercado

Los históricos se piden a Yahoo usando el ticker sin sufijo de mercado. `AAPL` representa la
acción estadounidense, no el CEDEAR de BYMA; `GGAL` puede representar el ADR y varios bonos
locales pueden no devolver datos. Por eso los indicadores no necesariamente corresponden al
instrumento registrado.

#### Media — Fallos de indicadores se convierten en valores aparentemente reales

Ante cualquier excepción se muestran RSI/MACD/volatilidad en cero y medias móviles iguales al
costo promedio, sin marcar que son valores de respaldo
([`portfolio/business.py`](portfolioar/portfolio/business.py#L278)).

#### Arquitectura — INDEC se consulta desde negocio

`ExternalAPIs.get_indec_inflation` usa `requests` directamente en `business.py`, aunque la
arquitectura exige que las APIs externas estén en `data_access.py`.

### Dictamen

**Dictamen original: parcial. Dictamen actualizado: cumple.** Los valores externos ausentes se
exponen como “No disponible”, S&P 500 se compara contra retorno de posición en USD, y se usan
Fisher/CAGR y períodos ponderados. Desde Fase 0, detalle y dashboard calculan performance una
sola vez por posición y pasan esa misma instantánea a ambas comparaciones, evitando requests y
resultados inconsistentes dentro de una misma carga.

### Criterio para considerarlo cerrado

- Representar la ausencia de precio/INDEC/S&P como estado explícito, nunca como cero.
- Implementar el camino alternativo visible de CU02.
- Definir una moneda base y normalizar posición y benchmark.
- Corregir rendimiento real y anualizado.
- Definir tratamiento de múltiples flujos y posiciones cerradas.
- Mapear cada instrumento al símbolo/mercado correcto para IOL y Yahoo.
- Mover las consultas externas a datos y agregar tests de contrato o integración controlada.

---

## CU03 – Configurar una alerta técnica

### Comportamiento documentado

Con indicadores y condiciones existentes, el usuario crea una alerta, selecciona instrumento,
agrega una o más condiciones válidas y la deja activa para evaluación. Las condiciones se
combinan con lógica AND.

### Implementación encontrada

1. La UI permite crear una alerta indicando instrumento, nombre y estado activo.
2. En el detalle se pueden asociar condiciones globales existentes.
3. `ConditionManager` valida los operadores permitidos por RN05.
4. `AlertManager.evaluate_alert` exige que todas las condiciones se cumplan.
5. `evaluate_alerts` procesa alertas activas y crea registros `AlertTrigger`.
6. El historial aparece en el detalle de la alerta.

### Qué cumple

- Autenticación y aislamiento de lectura por usuario.
- Creación, activación/desactivación y asociación de condiciones.
- Validación de nombre obligatorio.
- Lógica AND correcta ante condiciones y valores disponibles.
- Una alerta sin condiciones o sin un indicador requerido no se dispara.
- Historial persistido y visible.
- Comando idempotente de catálogo de indicadores.
- Tests unitarios y HTTP del flujo principal y de la evaluación AND.

### Brechas

#### Crítica — No se pueden crear condiciones desde la aplicación

La vista `condition_list` solo lista condiciones. No existe formulario, URL ni vista para
elegir indicador, operador y umbral. El seed crea `TechnicalIndicator`, pero no crea
`AlertCondition`. En una instalación nueva, el selector del detalle está vacío y CU03 no se
puede completar sin entrar al admin o escribir datos manualmente.

#### Alta — Editar el instrumento no funciona

El formulario de edición muestra el selector de acción, pero `alert_update` ignora
`stock_id`; solo actualiza nombre y estado
([`alerts/views.py`](portfolioar/alerts/views.py#L53)). La interfaz promete una modificación
que no se guarda.

#### Alta — La periodicidad no está garantizada por la aplicación

Existe un comando que realiza una evaluación, pero solo se vuelve periódico si alguien
configura cron en el ambiente desplegado. El repositorio no contiene evidencia de que esa
programación esté instalada. RF10 está preparado para calendarización, no ejecutándose
periódicamente por sí mismo.

#### Alta — Se crea un disparo en cada ejecución mientras la condición siga verdadera

No existe detección de transición falso→verdadero, cooldown ni deduplicación. Con cron cada
15 minutos, una condición sostenida durante un día genera hasta 96 disparos iguales.

#### Alta — El mercado de los indicadores puede ser incorrecto

La evaluación reutiliza históricos de Yahoo por ticker simple. Para CEDEARs, acciones locales
y bonos puede consultar el subyacente extranjero, un ADR o ningún instrumento. Una alerta
puede dispararse usando precios ajenos al activo que el usuario seleccionó.

#### Media — El período almacenado no gobierna el cálculo

`TechnicalIndicator.period` se guarda, pero el cálculo usa períodos fijos: RSI 14, MACD
12/26/9, SMA 20/50 y EMA 30. Cambiar el período desde admin no modifica la evaluación.

#### Media — RN05 no está garantizada en el modelo ni en la UI normal

La validación de operador vive en `ConditionManager.create`, pero no hay una UI que invoque
ese método. El admin y escrituras directas pueden guardar cualquier texto porque el modelo no
tiene `choices` ni restricción. Además, un operador inválido que llegue a evaluación no cae en
ninguna rama y puede terminar considerado satisfecho.

#### Media — La prohibición de umbrales negativos limita MACD

No surge de RN05 y hace imposible configurar, por ejemplo, `MACD < -1`, una condición válida
para un indicador que naturalmente puede ser negativo.

#### Media — Diagnóstico insuficiente de APIs

Los fallos al obtener históricos se absorben y devuelven un diccionario vacío. La alerta queda
“omitida”, pero no se registra cuál servicio o ticker falló. El contador `errors` puede seguir
en cero porque el error ya fue ocultado dentro de PortfolioManager.

#### Seguridad — Acciones destructivas mediante GET

Eliminar alertas y quitar condiciones se realiza con enlaces GET. Esas operaciones deberían
requerir POST con CSRF.

### Dictamen

**Dictamen original: parcial. Dictamen actualizado: cumple con reservas operativas.** Un
usuario puede crear condiciones custom desde la aplicación, editar el instrumento, y las
acciones destructivas usan POST con CSRF. RN05 se valida también en la base de datos. La
deduplicación acordada aplica un cooldown persistido de 15 minutos por alerta. La
calendarización y el mapeo de símbolos continúan siendo configuración/limitación del entorno.
Desde Fase 0 los umbrales negativos son válidos, por lo que se puede configurar y evaluar
`MACD < -1`.

### Criterio para considerarlo cerrado

- Permitir crear condiciones desde la UI o sembrar un catálogo de condiciones explícitamente
  aceptado por el equipo.
- Hacer que edición y formulario ofrezcan exactamente los campos que se persisten.
- Configurar y verificar el scheduler en el entorno de despliegue.
- Definir política de rearmado, cooldown o deduplicación.
- Resolver símbolos por mercado e instrumento.
- Aplicar RN05 en modelo/negocio y permitir umbrales negativos cuando corresponda.
- Exponer errores operativos sin disparar con datos incompletos.
- Cambiar operaciones destructivas a POST.

---

## CU04 – Registrar venta de una posición

### Comportamiento documentado

El usuario elige una posición, cantidad, precios, moneda y fecha. El sistema valida cantidad
y precios, impide vender más de lo disponible, consume lotes FIFO, calcula P&L realizado,
acredita liquidez y cierra la posición cuando no quedan títulos.

### Implementación encontrada

1. La vista verifica que la posición pertenece al usuario y muestra la cantidad abierta.
2. Negocio valida cantidad, ambos precios y moneda.
3. `get_open_lots` reconstruye el remanente descontando consumos anteriores.
4. `compute_sale_consumption` recorre lotes ordenados por fecha e ID y consume FIFO.
5. `compute_realized_pnl` calcula resultados ARS y USD.
6. Se crean `Sale`, uno o más `SaleLot`, el crédito de efectivo y el nuevo estado.
7. Los tests verifican venta parcial, consumo FIFO, P&L, exceso de cantidad, crédito y cierre.

### Qué cumple

- Autenticación y pertenencia de la posición en la vista.
- Cantidad y precios positivos.
- Rechazo de ventas superiores a la cantidad disponible.
- FIFO determinista por fecha de compra e ID.
- Trazabilidad de qué lotes consumió cada venta.
- P&L realizado en ARS y USD.
- Crédito en la moneda elegida.
- Cierre automático al agotar los lotes.
- Cobertura de tests sólida para el camino secuencial normal.

### Brechas

#### Crítica — Venta no atómica

`Sale`, cada `SaleLot`, el movimiento de efectivo y el cambio de estado se guardan por separado
([`portfolio/business.py`](portfolioar/portfolio/business.py#L416)). Si una escritura falla,
puede quedar una venta parcial, sin crédito o con estado incorrecto.

#### Crítica — Dos ventas simultáneas pueden consumir los mismos títulos

La disponibilidad se calcula antes de escribir y no se bloquean la posición ni sus lotes con
`select_for_update`. Dos requests concurrentes pueden leer el mismo remanente y ambas aprobar
la venta, produciendo sobreventa.

#### Alta — Los precios ARS y USD son independientes y confiados al usuario

El formulario exige ambos precios sin validar su relación mediante CCL. El usuario puede
ingresar valores incompatibles y elegir qué moneda acreditar. Eso permite generar P&L y
liquidez USD arbitrarios a partir de una misma venta.

#### Alta — Las comisiones no forman parte del P&L

Las comisiones de compra almacenadas en `Lot.fees` no integran el costo FIFO y no existe una
comisión de venta. El P&L realizado queda sobreestimado cuando hubo gastos.

#### Alta — Fechas de venta incoherentes son aceptadas

No se rechaza una venta anterior a los lotes que consume ni una fecha futura. Esto rompe la
cronología y puede afectar reportes posteriores.

#### Media — Datos malformados producen error 500

Al igual que CU01, `int()` y `float()` se ejecutan antes del `try`. No se utiliza un formulario
Django para validar y conservar los valores ingresados
([`portfolio/views.py`](portfolioar/portfolio/views.py#L183)).

#### Media — `recupero` mezcla conceptos contables

`CashTransaction.tipo='recupero'` representa tanto fondos obtenidos por una venta como
devoluciones causadas por borrar una compra. Esto dificulta auditar el origen económico de
los movimientos.

#### Media — Reglas solo en negocio

Los modelos `Sale` y `SaleLot` no tienen constraints positivos. Una escritura directa puede
crear cantidades o precios inválidos.

#### Media — Falta cobertura de fallos intermedios y concurrencia

Los tests comprueban correctamente FIFO y el camino HTTP, pero no simulan una excepción entre
las escrituras, ventas concurrentes, fechas inválidas, precios inconsistentes o comisiones.

### Dictamen

**Dictamen original: cumplimiento secuencial con riesgo crítico. Dictamen actualizado:
cumple.** La venta usa transacción y bloqueos FIFO, valida entradas y fechas, y registra tipos
contables diferenciados. Desde Fase 0 el formulario pide un único precio en la moneda elegida;
negocio deriva la contraparte ARS/USD mediante el CCL vigente o rechaza la venta si ese dato no
está disponible.

### Criterio para considerarlo cerrado

- Encapsular toda la venta en `transaction.atomic` desde la capa de datos.
- Bloquear los lotes/posición durante la validación y consumo.
- Validar request con `Decimal`, fechas y valores finitos.
- Definir una fuente o regla de conversión entre ARS y USD.
- Incorporar comisiones al costo y producido, o excluirlas formalmente del alcance.
- Separar venta, devolución y otros tipos de movimiento de efectivo.
- Añadir constraints y pruebas de rollback/concurrencia.

---

## Brechas transversales

### Formularios y validación

Las operaciones financieras procesan `request.POST` manualmente. Django Forms permitiría
validación tipada, mensajes por campo, preservación de valores y manejo consistente de fechas,
decimales y elecciones.

### Atomicidad

Compra y venta actualizan varias tablas sin una unidad transaccional. Es la mayor brecha de
integridad compartida por CU01 y CU04.

### Datos externos

Los fallos se convierten frecuentemente en ceros o valores de respaldo indistinguibles de
datos reales. Cada métrica externa necesita estado: disponible, no disponible, desactualizada
o estimada.

### Monedas

El proyecto almacena valores ARS y USD, pero no conserva el tipo de cambio ni su fuente en
cada operación. Sin esa trazabilidad, las comparaciones cruzadas y el P&L en ambas monedas no
son auditables.

### Tests

Los 119 tests actuales son valiosos para regresión del comportamiento implementado, pero que
un test pase no demuestra que la fórmula o el fallback sean correctos. Algunos tests fijan
como esperado un comportamiento que contradice la documentación, como mostrar inflación 0%
cuando INDEC falla.

## Orden recomendado de remediación

1. **Integridad de CU01/CU04:** transacciones atómicas, bloqueo de ventas, formularios y
   constraints.
2. **Exactitud de CU02:** estados de error explícitos, moneda común, fórmulas correctas y
   tratamiento de flujos múltiples.
3. **Usabilidad de CU03:** creación/seed de condiciones, edición coherente y scheduler real.
4. **Trazabilidad financiera:** tipo de cambio, comisiones y tipos de movimientos de efectivo.
5. **Datos de mercado:** mapeo de símbolos por instrumento/mercado y pruebas controladas de
   las integraciones.

## Resultado final

La fotografía inicial no permitía afirmar cobertura completa. Tras Fases 0–4 verificadas:

- **CU01:** compra consistente y transaccional.
- **CU02:** cálculo con monedas y fórmulas correctas; fallos externos visibles y performance
  reutilizado en comparaciones.
- **CU03:** flujo completo de configuración desde UI; cooldown de 15 minutos y umbrales MACD
  negativos habilitados.
- **CU04:** FIFO transaccional y protegido frente a sobreventa concurrente; precio único
  validado mediante CCL.

Las brechas fuera de alcance permanecen explicitadas como limitaciones operativas y no
invalidan los caminos documentados.
