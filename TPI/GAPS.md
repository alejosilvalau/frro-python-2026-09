# Gaps: Requerimientos y Casos de Uso faltantes

Análisis de `PROYECTO.md` contra la implementación actual. Lista de requerimientos funcionales y casos de uso declarados pero **no implementados** (o implementados a medias).

## RF11 – Asistente IA (LangChain + LLM) — NO IMPLEMENTADO

- `langchain` y `openai` están en `requirements.txt` pero **ningún módulo los importa**.
- No existe el asistente que interpreta resultados, contextualiza indicadores, compara benchmarks ni hace predicción/recomendación.
- Referencias: `PROYECTO.md` RF11, capa de negocio ("integración con LangChain"), `.env.example` (`OPENAI_API_KEY`).

**A implementar:** servicio en capa de negocio que construya el prompt con métricas calculadas y llame al LLM (OpenAI o Gemini vía LangChain).

## RF10 – Evaluación periódica de alertas — NO IMPLEMENTADO

- `evaluate_alert` existe (`alerts/business.py:65`) pero **nadie lo invoca**.
- No hay scheduler, Celery, cron ni management command.
- `AlertTrigger` (historial de disparos) existe como modelo, pero `trigger_alert` solo corre si se llama manualmente; no hay vista ni comando que lo dispare.

**A implementar:** tarea programada (management command + cron, o Celery beat) que evalúe las alertas activas de cada usuario y registre los disparos en `AlertTrigger`.

## RF06 – Análisis de correlación — NO IMPLEMENTADO

- `calculate_portfolio_summary` (`portfolio/business.py:150-194`) devuelve: total invertido, valor actual, ganancia/pérdida total, alpha y distribución por sector.
- **No existe** análisis de correlación entre posiciones.
- Volatilidad por posición sí está calculada (vía `get_technical_indicators`, campo `volatility`).

**A implementar:** matriz de correlación de retornos entre posiciones (pandas) agregada al resumen del portfolio.

## RF09 – Cruce de MACD — NO SOPORTADO

- El modelo de condición = `indicador + operador + umbral` (`alerts/models.py:20-31`).
- `evaluate_alert` compara un único valor actual contra un umbral con operadores `> < >= <= == !=`.
- Un **cruce de MACD** (MACD cruzando la señal) requiere comparar dos series temporales; no es modelable como condición simple.

**A implementar:** nuevo tipo de condición de cruce (indicador A vs indicador B) o lógica dedicada en `evaluate_alert`.

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
| RF06 | Parcial (falta correlación) |
| RF07 | Implementado |
| RF09 | Parcial (sin cruce MACD, sin seed) |
| RF10 | Parcial (modelo OK, sin scheduler) |
| RF11 | No implementado |
| CU01–CU03 | Implementado |
| CU venta | Faltante |