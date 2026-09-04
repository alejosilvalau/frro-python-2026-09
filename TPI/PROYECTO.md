# PortfolioAR
## Descripción del proyecto
PortfolioAR es una aplicación web orientada a inversores argentinos que operan en mercados de acciones y bonos locales e internacionales a través de CEDEARs. La plataforma permite gestionar la cartera de inversiones de forma centralizada, obteniendo métricas reales de rendimiento, análisis técnico automatizado y alertas configurables basadas en indicadores financieros.

El diferencial clave del sistema es contextualizar el rendimiento de cada inversión no solo en términos absolutos, sino comparándolo contra el índice S&P 500 y contra la inflación argentina oficial del mismo periodo, respondiendo la pregunta central del inversor retail argentino: **¿le gané a la inflación?**

El sistema resuelve los siguientes problemas concretos:

- El acceso a herramientas de análisis financiero profesional en Argentina requiere mucho conocimiento sobre el mercado.
- El inversor retail no tiene una forma simple de saber si su cartera realmente le ganó a la inflación o al mercado.
- No existe una herramienta que combine seguimiento de portfolio y alertas técnicas en un solo lugar, en español y orientada a Argentina.

## Modelo de Dominio

![Diagrama de Clases](./diagrama-de-clases-v2.jpg)

## Bosquejo de Arquitectura

El sistema sigue una arquitectura de 3 capas:

![Bosquejo de Arquitectura](./bosquejo-de-arquitectura-v1.png)

División horizontal de responsabilidades:
- La **capa de presentación** expone vistas Django y renderiza los templates. No accede directamente a la base de datos.
- La **capa de negocio** concentra todos los cálculos de rendimiento, indicadores técnicos y evaluación de alertas. No contiene elementos de interfaz.
- La **capa de datos** gestiona todas las consultas a SQL Server mediante el Django ORM (con `mssql-django`) y las llamadas a APIs externas (IOL, INDEC).

División vertical por casos de uso:
- Auth: Gestión de usuarios (registro, login, logout y cambios de contraseña).
- Portfolio: Registro de posiciones y ordenes de venta.
- Alerts : Configuración y evaluación de alertas técnicas.

## Requerimientos

### Funcionales

**Módulo 1 – Gestión de Portfolio**

- RF01: El usuario puede registrarse, iniciar sesión y cerrar sesión.
- RF02: El usuario puede registrar operaciones de compra y venta de acciones, bonos y CEDEARs (ticker, cantidad, precio, fecha).
- RF03: El sistema calcula el rendimiento de cada posición: precio de compra vs. precio actual, ganancia/pérdida en % y en dólares, rendimiento anualizado.
- RF04: El sistema compara el rendimiento de cada posición contra el S&P 500 (SPY) para el mismo período.
- RF05: El sistema compara el rendimiento del portfolio contra la inflación acumulada del INDEC para el período de inversión.
- RF07: El sistema calcula y muestra indicadores técnicos actuales por posición.

**Módulo 2 – Alertas**

- RF10: El sistema evalúa periódicamente las condiciones de alerta y registra los disparos en el historial.

### No Funcionales

### Portability

**Obligatorios**

- El sistema funciona correctamente en múltiples navegadores (Chrome, Firefox, Edge).

### Security

**Obligatorios**

- Todas las contraseñas se guardan con encriptado criptográfico (SHA-256 o bcrypt).
- Todas las API Keys y tokens (IOL) no se exponen de manera pública (uso de variables de entorno / `.env`).

### Maintainability

**Obligatorios**

- El posee diseñarse con la arquitectura en 3 capas. (Ver [checklist_capas.md](checklist_capas.md))
- El utiliza utilizar control de versiones mediante GIT.
- El sistema está programado en Python 3.8 o superior.

### Reliability

- Se maneja correctamente la ausencia de datos para períodos sin cotización (feriados, fines de semana).

### Scalability

**Obligatorios**

- El sistema funciona desde una ventana normal y una de incógnito de manera independiente (multiusuario).
- La sesión de usuario se gestiona mediante el sistema de sesiones de Django, sin variables locales.

### Performance

**Obligatorios**

- El sistema funciona en un equipo hogareño estándar.

### Reusability

- La capa de datos expone funciones reutilizables para consultar la APIs utilizadas (IOL, INDEC), independientemente del módulo que las consuma.

### Flexibility

**Obligatorios**

- El sistema utiliza SQL Server como base de datos relacional, accedido mediante el Django ORM con el backend `mssql-django`.

## Stack Tecnológico

### Capa de Datos

- **SQL Server**: motor relacional robusto, ampliamente utilizado en entornos empresariales. Almacena todas las entidades del dominio.
- **Django ORM + mssql-django**: el ORM incluido en Django, con el backend oficial de Microsoft para SQL Server (`mssql-django`). Permite definir los modelos como clases Python y gestionar migraciones sin escribir SQL directamente, facilitando el cambio de motor de base de datos si fuera necesario.
- **API IOL (InvertirOnline)**: API REST oficial del broker argentino InvertirOnline. Requiere cuenta en IOL y autenticación por token (OAuth2). Provee cotizaciones en tiempo real e históricas de acciones, bonos y CEDEARs del mercado argentino (BYMA) e internacional. Se utiliza para obtener los precios necesarios para calcular el rendimiento de las posiciones y alimentar los snapshots diarios.
- **API INDEC (datos.gob.ar)**: API REST pública del INDEC para obtener la variación mensual del IPC nacional. Gratuita, sin autenticación. Endpoint: `https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26&format=json`

### Capa de Negocio

- **pandas**: manipulación y análisis de series temporales de precios. Central para el cálculo de métricas de rendimiento y estadísticas.
- **pandas-ta**: extensión de pandas para el cálculo de indicadores técnicos (RSI, MACD, volumen relativo, desviación estándar de retornos, etc.).

### Capa de Presentación

- **Django**: framework web completo (batteries included). Se eligió por su ORM integrado, sistema de autenticación y gestión de sesiones listos para usar, panel de administración y alta demanda laboral en el mercado argentino. 
- **Django Templates**: sistema de templates incluido en Django para renderizar las vistas del portfolio, alertas y análisis. Permite migrar a React en el futuro si se desea separar el frontend.

## Reglas de Negocio

- **RN01 – Contraseña mínima**: La contraseña del usuario debe tener como mínimo 8 caracteres. El registro y el cambio de contraseña fallan si no se cumple esta condición.
- **RN02 – Email único**: No pueden existir dos usuarios registrados con el mismo correo electrónico. El sistema rechaza el registro si el email ya está en uso.
- **RN03 – Cantidad positiva**: La cantidad de títulos al registrar una posición o una orden debe ser mayor a cero.
- **RN04 – Precio positivo**: El precio de compra al registrar una posición debe ser mayor a cero.
- **RN05 – Operadores válidos**: Los operadores de condición de alerta deben ser uno de los siguientes: `>`, `<`, `>=`, `<=`, `==`, `!=`. Cualquier otro operador es rechazado.
- **RN06 – Evaluación AND de alertas**: Una alerta se dispara únicamente si **todas** sus condiciones se cumplen de forma simultánea (lógica AND). Si alguna condición no se cumple, la alerta no se dispara aunque el resto sí lo hagan.

## Casos de Uso Principales

### CU01 – Registrar posición de compra

| Campo | Descripción |
| --- | --- |
| **Actor** | Usuario autenticado |
| **Precondición** | El usuario inició sesión. El ticker de la acción existe en el sistema. |
| **Camino básico** | 1. El usuario navega a "Posiciones → Nueva posición". 2. Completa ticker, cantidad, precio de compra, broker y fecha. 3. El sistema valida RN03 y RN04. 4. La posición se guarda y redirige al listado. |
| **Camino alternativo** | Si cantidad ≤ 0 o precio ≤ 0, el sistema muestra un error y no guarda la posición. |

### CU02 – Consultar rendimiento de una posición

| Campo | Descripción |
| --- | --- |
| **Actor** | Usuario autenticado |
| **Precondición** | El usuario tiene al menos una posición registrada. |
| **Camino básico** | 1. El usuario accede al detalle de una posición. 2. El sistema obtiene el precio actual, calcula ganancia/pérdida absoluta y porcentual. 3. Compara el rendimiento contra el S&P 500 y contra la inflación INDEC del período. 4. Muestra los resultados con indicadores de color (verde/rojo). |
| **Camino alternativo** | Si la API del INDEC no responde, se muestra un mensaje de error y se omite la comparación de inflación. |

### CU03 – Configurar una alerta técnica

| Campo | Descripción |
| --- | --- |
| **Actor** | Usuario autenticado |
| **Precondición** | Existen indicadores técnicos y condiciones cargadas en el sistema. |
| **Camino básico** | 1. El usuario navega a "Alertas → Nueva alerta". 2. Selecciona acción y nombre. 3. Desde el detalle de la alerta, agrega una o más condiciones existentes. 4. El sistema valida RN05. 5. La alerta queda activa y lista para ser evaluada. |
| **Camino alternativo** | Si el operador de alguna condición no es válido (RN05), el sistema rechaza la condición con un mensaje de error. |

## Bibliografía

- Django Software Foundation. *Django documentation* (v4.2). <https://docs.djangoproject.com/en/4.2/>
- Microsoft. *mssql-django – SQL Server backend for Django*. <https://github.com/microsoft/mssql-django>
- The pandas development team. *pandas documentation*. <https://pandas.pydata.org/docs/>
- pandas-ta contributors. *pandas-ta: Technical Analysis Indicators*. <https://github.com/twopirllc/pandas-ta>
- InvertirOnline. *API IOL – Documentación oficial*. <https://api.invertironline.com/>
- Ministerio de Economía, Argentina. *API de Series de Tiempo – INDEC IPC*. <https://apis.datos.gob.ar/>

## Documentación de Librerías

| Librería | Versión | Uso en el proyecto |
| --- | --- | --- |
| Django | ≥ 4.2 | Framework web principal. ORM, vistas, templates, autenticación y sesiones. |
| mssql-django | ≥ 1.3 | Backend de Django para conectarse a SQL Server en producción. |
| python-dotenv | — | Carga variables de entorno desde `.env` en desarrollo local. |
| requests | — | Llamadas HTTP a las APIs externas (IOL, INDEC). |
| pandas | — | Manipulación de series temporales de precios para cálculos de rendimiento. |
| pandas-ta | — | Cálculo de indicadores técnicos (RSI, MACD, etc.) sobre series de precios. |
| pytest | — | Framework de tests. |
| pytest-django | — | Plugin de pytest para proyectos Django (fixtures, settings de test). |

## Link al Código Fuente

Repositorio: https://github.com/alejosilvalau/frro-python-2026-09/tree/tpi
