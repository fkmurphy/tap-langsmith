
# tap-langsmith

Singer tap para extraer datos de ejecuciones (runs) de [LangSmith](https://smith.langchain.com/) mediante la API oficial.

## Descripción

Este tap permite extraer datos de trazas (traces) y ejecuciones de LangSmith en formato Singer, compatible con Meltano y otros orquestadores de pipelines de datos. Soporta replicación incremental basada en `start_time` para procesar solo registros nuevos o modificados.

## Requisitos

- Python 3.8 o superior
- pip o Poetry para gestionar dependencias
- Credenciales válidas de LangSmith (API key y session ID)

## Instalación

### Con pip
pip install git+https://github.com/fkmurphy/tap-meltano-langsmith.git


### Con poetry
poerty install


## Configuración

El tap requiere los siguientes parámetros:

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `api_key` | string | ✅ | Tu API key de LangSmith (obtén en https://smith.langchain.com/settings/api-keys) |
| `session_id` | string | ✅ | El ID de sesión de LangSmith que deseas monitorear |
| `start_time` | string | ❌ | Fecha de inicio en ISO 8601 (ej: `2025-01-01T00:00:00Z`). Si no se especifica, procesa desde el inicio |


### Configuración en Meltano

```
extractors:

name: tap-langsmith
variant: custom
pip_url: git+https://github.com/tu-usuario/tap-langsmith.git
executable: tap-langsmith
config:
api_key: ${LANGSMITH_API_KEY}
session_id: ${LANGSMITH_SESSION_ID}
start_time: ${LANGSMITH_START_TIME}
```

## Uso

### Línea de comandos

tap-langsmith --config config.json


### Con Meltano

meltano run tap-langsmith target-jsonl


## Esquema de datos

El tap extrae los siguientes campos de cada ejecución (run):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `trace_id` | string | Identificador único de la traza |
| `status` | string | Estado de la ejecución (success, error, etc.) |
| `name` | string | Nombre de la ejecución |
| `start_time` | datetime | Hora de inicio (clave de replicación) |
| `end_time` | datetime | Hora de finalización |
| `inputs` | object | Parámetros de entrada |
| `outputs` | object | Resultados de salida |
| `error` | string | Mensaje de error si aplica |
| `total_tokens` | integer | Tokens consumidos |
| `total_cost` | number | Costo total estimado |
| `first_token_time` | string | Hora del primer token |
| `trace_min_max_start_time` | string | Rango de tiempo de la traza |
| `ttl_seconds` | string | Tiempo de vida del registro |
| `thread_id` | string | ID del thread asociado |
| `extra` | object | Metadatos adicionales |

## Características

- ✅ Replicación incremental basada en timestamp
- ✅ Configuración de fecha de inicio personalizable
- ✅ Paginación automática con cursor
- ✅ Filtrado de runs raíz (`is_root: true`)
- ✅ Compatible con Singer estándar
- ✅ Soporte para Meltano y herramientas Singer

## Pruebas locales
poetry run tap-langsmith --config config.json | head -20

## Limitaciones

- La replicación incremental usa `start_time` como clave
- El tap solo extrae runs raíz (ejecuciones principales)
- La paginación está limitada a 100 registros por página
