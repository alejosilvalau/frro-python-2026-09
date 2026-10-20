# Gaps: Requerimientos y Casos de Uso

Análisis de `PROYECTO.md` contra la implementación actual. A la fecha no quedan requerimientos
funcionales ni casos de uso documentados pendientes de implementación: la Fase 0 de
[`plan.md`](plan.md) cerró los tres desajustes verificados restantes.

> **Nota**: RF06 (análisis de correlación), RF09 (alertas técnicas avanzadas / cruce de MACD) y RF11 (asistente IA) fueron **removidos como requisito** de `PROYECTO.md` por decisión del equipo. El código que ya cubría partes de RF06 y RF09 (resumen de portfolio, alertas por RSI/precio/volumen) se mantiene funcionando como funcionalidad no exigida por la consigna; no se documentan más gaps sobre ellos.

## RF10 – Evaluación periódica de alertas — IMPLEMENTADO

- `python manage.py evaluate_alerts` procesa las alertas activas y registra los disparos en `AlertTrigger`.
- La lógica omite alertas sin condiciones o sin todos los datos de mercado requeridos.
- Cada alerta aplica un cooldown persistido de 15 minutos para no duplicar disparos mientras
  la condición se mantiene verdadera.
- `PROYECTO.md` documenta cómo programar el comando periódicamente con cron.
- El historial de disparos se muestra en el detalle de cada alerta.

## Catálogo de indicadores técnicos — IMPLEMENTADO

- `python manage.py seed_technical_indicators` crea o actualiza de manera idempotente RSI, MACD, SMA 20/50, EMA 30, volumen relativo y volatilidad.
- `seed_demo_data` ejecuta automáticamente este seed para dejar el entorno local utilizable.

## Caso de uso de venta — IMPLEMENTADO Y DOCUMENTADO

- El refactor de `Position`/`Lot`/`Sale` (costeo FIFO) implementó por completo la venta: `SaleManager.add_sale` consume lotes por FIFO, calcula P&L realizado, acredita liquidez automáticamente y cierra la posición cuando corresponde.
- La venta recibe un único precio en la moneda seleccionada y deriva la contraparte ARS/USD con
  el CCL vigente; si CCL no está disponible, no se registra la operación.
- Cubierto por tests (`SaleFIFOTest`, `SaleViewTest`) y accesible desde la UI vía el menú "Operar → Vender".
- `PROYECTO.md` incluye CU04 con el camino básico FIFO y sus validaciones alternativas.

## Desajustes menores resueltos

- **NFR Security**: la documentación refleja el uso real de PBKDF2 mediante Django.
- **Snapshots diarios**: se retiró la mención porque no formaban parte de ningún RF ni caso de uso.
- **Movimientos de liquidez**: `CashTransaction` distingue `compra`, `venta` y
  `reembolso por eliminación`; la migración conserva y clasifica los recuperos históricos.
- **Cálculo repetido de rendimiento**: detalle y dashboard reutilizan una misma instantánea de
  performance para S&P 500 e inflación, evitando consultas externas redundantes.
- **MACD negativo**: los umbrales negativos son válidos en negocio y UI; por ejemplo,
  `MACD < -1` puede configurarse y evaluarse.
- **RF01–RF05, RF07, CU01–CU03**: implementados y funcionales ✓.
- **RF10 histórico**: el modelo, la evaluación y la consulta del historial están implementados ✓.

## Checklist resumen

| Ítem | Estado |
| --- | --- |
| RF01–RF05 | Implementado |
| RF07 | Implementado |
| RF10 | Implementado (comando programable + historial) |
| CU01–CU03 | Implementado |
| CU04 venta | Implementado y documentado |

## Operaciones históricas — IMPLEMENTADO

- Las operaciones nuevas guardan un snapshot de precio, CCL, fecha, fuente, moneda de entrada y
  unidad de cotización. El historial no se recalcula con una cotización actual.
- IOL aporta último precio intradía para hoy y serie diaria sin ajustar para fechas pasadas;
  ArgentinaDatos aporta el CCL de la fecha. Si el CCL falta, el usuario puede confirmarlo
  manualmente.
- Bonos y letras usan cantidad en VN y precio cada 100 VN. Queda fuera de alcance registrar
  cupones y amortizaciones como movimientos de liquidez.
- Cada instrumento guarda su moneda de negociación; las compras se restringen a esa moneda y el
  formulario avisa cuando falta liquidez o broker.
- Los formularios de compra y venta muestran el gráfico histórico del instrumento.

## Catálogo y clasificación de instrumentos — IMPLEMENTADO

- `seed_instruments_from_iol` importa acciones, CEDEARs, bonos y letras desde IOL junto con su
  moneda de negociación, y siembra los brokers fijos.
- `sync_instrument_classification` aplica una clasificación versionada (sector, tipo de CEDEAR,
  emisor, tasa, estilo de pago) con fuente y fecha, respetando ediciones manuales.

## Rendimiento y comparaciones — IMPLEMENTADO

- Si el período de tenencia no alcanza la granularidad del benchmark (S&P 500 diario, inflación
  INDEC mensual), se compara contra una ventana de 12 meses y la UI lo indica.
- El % de ganancia/pérdida de la cartera se calcula sobre el capital total invertido (abierto y
  cerrado), por lo que ya no queda vacío con carteras totalmente cerradas.
- Las cotizaciones en USD se convierten antes de calcular el P&L en ARS.

## Alertas desde el sitio — IMPLEMENTADO

- Con sesión abierta, el navegador evalúa las alertas del usuario (máximo una vez cada 15
  minutos por sesión) y avisa si hubo un disparo o faltan datos históricos.
- Los indicadores de especies BYMA usan el símbolo de Yahoo con sufijo `.BA`; sin histórico
  suficiente no se generan indicadores ficticios.
