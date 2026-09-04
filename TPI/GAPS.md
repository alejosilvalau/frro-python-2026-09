# Gaps: Requerimientos y Casos de Uso faltantes

Análisis de `PROYECTO.md` contra la implementación actual. Lista de requerimientos funcionales y casos de uso declarados pero **no implementados** (o implementados a medias).

> **Nota**: RF06 (análisis de correlación), RF09 (alertas técnicas avanzadas / cruce de MACD) y RF11 (asistente IA) fueron **removidos como requisito** de `PROYECTO.md` por decisión del equipo. El código que ya cubría partes de RF06 y RF09 (resumen de portfolio, alertas por RSI/precio/volumen) se mantiene funcionando como funcionalidad no exigida por la consigna; no se documentan más gaps sobre ellos.

## RF10 – Evaluación periódica de alertas — NO IMPLEMENTADO

- `evaluate_alert` existe (`alerts/business.py:65`) pero **nadie lo invoca**.
- No hay scheduler, Celery, cron ni management command.
- `AlertTrigger` (historial de disparos) existe como modelo, pero `trigger_alert` solo corre si se llama manualmente; no hay vista ni comando que lo dispare.

**A implementar:** tarea programada (management command + cron, o Celery beat) que evalúe las alertas activas de cada usuario y registre los disparos en `AlertTrigger`.

## Indicadores técnicos sin seed — NO UTILIZABLE OUT-OF-THE-BOX

- `TechnicalIndicator` no tiene fixtures. `initial_data.json` solo carga `Sector`, `Broker` y `Stock`.
- El catálogo de indicadores (RSI, MACD, etc.) queda vacío salvo que un admin los cree a mano.

**A implementar:** seed de indicadores (RSI, MACD, SMA 20/50, EMA 30, volumen relativo, volatilidad) en fixture o management command.

## Caso de uso de venta/orden — FALTANTE

- RF02 declara "operaciones de compra **y venta**", pero solo hay CU01 (registrar posición de compra).
- `order_create` existe (`portfolio/views.py:145`) pero sin CU documentado, y **no descuenta la cantidad de la posición**: la orden queda como registro suelto sin afectar el portfolio.

**A implementar:** CU de venta documentado en `PROYECTO.md` y, si corresponde, lógica que reduzca `Position.amount` al registrar la orden.

## Desajustes menores (doc vs código)

- **NFR Security**: `PROYECTO.md` exige "SHA-256 o bcrypt"; Django usa **PBKDF2** por defecto (cifrado más robusto, pero la documentación no coincide con la implementación).
- **Snapshots diarios**: el stack describe snapshots diarios alimentados por IOL; **no existe** modelo `Snapshot` ni scheduler que los genere.
- **RF01–RF05, RF07, CU01–CU03**: implementados y funcionales ✓.
- **RF10 histórico**: el modelo `AlertTrigger` existe ✓ (falta solo la evaluación periódica).

## Checklist resumen

| Ítem | Estado |
| --- | --- |
| RF01–RF05 | Implementado |
| RF07 | Implementado |
| RF10 | Parcial (modelo OK, sin scheduler) |
| CU01–CU03 | Implementado |
| CU venta | Faltante |