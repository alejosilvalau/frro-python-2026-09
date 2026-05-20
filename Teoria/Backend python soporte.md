Aquí tienes el documento técnico (Technical Design Document) estructurado para el proyecto. Está redactado en formato Markdown, listo para ser copiado a un archivo `README.md` o a la wiki del repositorio (ej. Confluence/Notion), enfocado estrictamente en arquitectura, stack y responsabilidades de capa.

***

# Arquitectura Backend - EspaciosYa

## 1. Stack Tecnológico Base
El proyecto utiliza un stack moderno, fuertemente tipado y asíncrono, optimizado para operaciones I/O bound.

* **Lenguaje:** Python 3.10+ (Tipado estricto mediante Type Hints).
* **Framework Core:** FastAPI (Ruteo HTTP, OpenAPI autogenerado, Inyección de Dependencias).
* **Servidor ASGI:** Uvicorn.
* **Base de Datos:** MySQL.
* **Driver de Conexión:** `aiomysql` (Conexión asíncrona no bloqueante).
* **ORM:** SQLAlchemy 2.0 (Patrón Data Mapper/Active Record mixto, soporte asíncrono).
* **Gestor de Migraciones:** Alembic.
* **Validación y Serialización:** Pydantic v2 (Validación por esquemas en tiempo de ejecución).
* **Testing:** Pytest, pytest-asyncio, HTTPX.
* **Entorno Local:** Docker Compose (Infraestructura), Makefile (Automatización de comandos).

---

## 2. Topología del Proyecto (Scaffolding)

```text
espacios_ya/
├── app/
│   ├── api/                    # Capa HTTP y Enrutamiento
│   │   ├── dependencies.py     # Inyectores (Session, CurrentUser)
│   │   ├── middlewares/        # Interceptores (CORS, Error handlers globales)
│   │   └── routes/             # Controladores (Endpoints)
│   │
│   ├── schemas/                # Data Transfer Objects (DTOs)
│   │   ├── space_schema.py     # Pydantic models (Validación I/O)
│   │   └── user_schema.py
│   │
│   ├── services/               # Lógica de Negocio (Casos de uso)
│   │   ├── space_service.py    # Orquestación de reglas de negocio
│   │   └── auth_service.py
│   │
│   ├── repositories/           # Capa de Acceso a Datos
│   │   ├── base.py             # Clase base genérica (Opcional)
│   │   └── space_repo.py       # Queries SQLAlchemy específicas
│   │
│   ├── models/                 # Modelos ORM (Entidades de BD)
│   │   ├── base.py             # DeclarativeBase de SQLAlchemy
│   │   └── space_model.py      # Definición de tabla, columnas y relaciones
│   │
│   ├── db/                     # Infraestructura de Base de Datos
│   │   └── session.py          # Configuración del Engine asíncrono
│   │
│   ├── core/                   # Configuraciones y utilidades transversales
│   │   ├── config.py           # Pydantic Settings (variables de entorno)
│   │   └── security.py         # JWT, Hashing de contraseñas (Passlib)
│   │
│   └── main.py                 # Entrypoint de la aplicación y registro de Routers
│
├── tests/                      # Suite de pruebas unitarias y de integración
├── alembic/                    # Historial de migraciones SQL
├── docker-compose.yml          # Definición de servicios (MySQL)
├── Makefile                    # Tareas de automatización (run, migrate, test)
├── requirements.txt            # Dependencias
└── .env                        # Variables de entorno secretas (No commiteado)
```

---

## 3. Implicancias y Restricciones por Capa

El diseño sigue una separación de responsabilidades pragmática. Las dependencias fluyen siempre desde afuera (API) hacia adentro (Modelos/Dominio).

### Capa 1: Presentación (`app/api/`)
* **Responsabilidad:** Manejar el protocolo HTTP. Es la única capa que sabe que el sistema es una API web.
* **Tecnología dominante:** FastAPI.
* **Reglas estrictas:**
  * **PROHIBIDO:** Ejecutar consultas SQL (ej. `db.query()`), aplicar reglas de negocio o instanciar modelos de base de datos.
  * **OBLIGATORIO:** Inyectar dependencias (Servicios) a través de los constructores/parámetros de las funciones de ruta usando `Depends()`.
  * **OBLIGATORIO:** Retornar siempre objetos serializables validados por un `Schema` de Pydantic.
* **Manejo de Errores:** Captura excepciones customizadas arrojadas por la capa de `services/` y las traduce a códigos HTTP estandarizados (400, 404, 409) usando `HTTPException`.

### Capa 2: DTOs y Validación (`app/schemas/`)
* **Responsabilidad:** Definir el contrato estático de la API. Validar los datos que entran en un request y filtrar los datos que salen en el response.
* **Tecnología dominante:** Pydantic v2.
* **Implicancia:** Actúa como un *firewall* de datos. Si un payload no cumple el schema, Pydantic rechaza la petición HTTP con un error 422 antes de que el controlador llegue a ejecutarse. Se usan schemas separados para entrada (`SpaceCreate`) y salida (`SpaceResponse`) para no filtrar campos sensibles.

### Capa 3: Lógica de Aplicación (`app/services/`)
* **Responsabilidad:** Contener el núcleo (Core) del negocio. Coordina la ejecución de una operación completa.
* **Reglas estrictas:**
  * **PROHIBIDO:** Recibir o devolver objetos de tipo Request/Response HTTP.
  * **PROHIBIDO:** Escribir consultas SQL crudas o directas.
  * **Flujo típico:** Recibe parámetros primitivos o Schemas validados -> Valida reglas de negocio (ej. "El usuario no tiene permisos para crear más salones") -> Llama a uno o más `repositories` -> Llama a servicios externos (ej. envío de correos) -> Retorna el resultado.

### Capa 4: Acceso a Datos (`app/repositories/`)
* **Responsabilidad:** Aislar la lógica de interacción con MySQL.
* **Tecnología dominante:** SQLAlchemy.
* **Implicancia:** Centraliza las consultas. Si la forma en que se recuperan los salones activos cambia, se modifica únicamente aquí. Recibe la `Session` (conexión de DB) inyectada. Ejecuta los métodos de agregación, inserción y manejo de transacciones (`commit`, `rollback`, `refresh`).

### Capa 5: Modelos y Dominio (`app/models/`)
* **Responsabilidad:** Definir la estructura física de los datos y las relaciones relacionales.
* **Tecnología dominante:** SQLAlchemy ORM (`DeclarativeBase`).
* **Implicancia:** En esta arquitectura pragmática, el modelo ORM funciona simultáneamente como entidad de dominio.
* **Regla:** Solo debe contener lógica intrínseca a la entidad (ej. métodos computados tipo `@property` para calcular el estado de ocupación de un salón basado en sus atributos). Cero dependencias externas.

---

## 4. Flujo de Vida de una Petición (Ejemplo: Crear un Salón)

1. **Cliente HTTP** envía POST `/api/v1/spaces` con un JSON.
2. **FastAPI (Router)** recibe el request.
3. **Pydantic (Schema)** intercepta el JSON. Verifica que `name` sea string y `capacity` sea mayor a 0. Construye el objeto `SpaceCreate`.
4. **Router** obtiene la instancia de `SpaceService` (con su repositorio y DB session inyectados por el dependency injection framework).
5. **SpaceService** recibe el schema. Verifica si existe alguna restricción de negocio (ej. cuota excedida).
6. **SpaceService** invoca a `SpaceRepository.create()`.
7. **SpaceRepository** mapea `SpaceCreate` al modelo ORM `SpaceModel`, lo añade a la sesión de SQLAlchemy y ejecuta `commit()`.
8. **MySQL** guarda el registro. El modelo ORM se actualiza con el ID autogenerado.
9. El dato viaja en reversa (Repo -> Service -> Router).
10. **Router** devuelve el objeto. FastAPI lo intercepta con `SpaceResponse` (Schema de salida) para serializarlo limpiamente, omitiendo columnas de auditoría internas, y envía HTTP 201.

---

## 5. Infraestructura y Migraciones

### Manejo del Esquema (Alembic)
Los modelos ORM son la "fuente de la verdad" del sistema. Los cambios en la base de datos se manejan mediante control de versiones de esquema.
* Todo cambio en la capa `models/` requiere la generación de una revisión de Alembic (`alembic revision --autogenerate`).
* Las migraciones se aplican en orden secuencial garantizando la idempotencia en cualquier entorno (desarrollo, staging, producción).

### Desarrollo Local (Docker & Makefile)
La carga cognitiva de preparar el entorno se elimina mediante contenedores.
* El motor MySQL corre estrictamente en un contenedor definido en `docker-compose.yml`.
* El archivo `Makefile` abstrae los comandos operacionales. (Ej. Ejecutar `make db-up` levanta la DB, `make run` levanta Uvicorn en modo watch, `make test` ejecuta la suite completa de Pytest aislando las sesiones de base de datos).


espacios_ya/
├── app/
│   ├── api/                    # Capa de Presentación (HTTP)
│   │   ├── dependencies.py     # Resolutores de inyección (ej: get_db, get_service)
│   │   ├── middlewares/        # Interceptores (CORS, Logging, Rate Limiting)
│   │   └── routes/             # Enrutadores (Endpoints agrupados por recurso)
│   │
│   ├── application/            # Capa de Aplicación (Casos de Uso y DTOs)
│   │   ├── schemas/            # DTOs en Pydantic (Validación de entrada/salida)
│   │   └── services/           # Orquestación y lógica de negocio pura
│   │
│   ├── domain/                 # Capa de Dominio (El Core)
│   │   ├── entities.py         # Clases de Python puras (Dataclasses) sin dependencias
│   │   ├── exceptions.py       # Excepciones personalizadas de negocio
│   │   └── interfaces.py       # Contratos (typing.Protocol) para repos y servicios
│   │
│   ├── infrastructure/         # Capa de Infraestructura (Adaptadores)
│   │   ├── database/
│   │   │   ├── session.py      # Configuración del Engine y Session Factory
│   │   │   └── models.py       # Modelos ORM (Mapeo a tablas SQL)
│   │   └── repositories/       # Implementación concreta del acceso a datos
│   │
│   ├── core/                   # Capa Transversal
│   │   ├── config.py           # Settings unificados (carga de .env usando Pydantic BaseSettings)
│   │   └── security.py         # Lógica transversal (Hashing, validación JWT)
│   │
│   └── main.py                 # Entrypoint: Inicialización de la app y registro de rutas
│
├── tests/                      # Suite de tests
│   ├── unit/                   # Tests aislando la capa de aplicación (mockeando repos)
│   └── integration/            # Tests contra DB de prueba (ej: testcontainers)
│
├── alembic/                    # Gestor de migraciones de la base de datos
├── pyproject.toml              # Definición de dependencias modernas (Poetry o UV)
└── .env                        # Variables de entorno locales