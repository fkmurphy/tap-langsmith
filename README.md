# tap-langsmith

Singer tap que extrae *runs* (ejecuciones) de [LangSmith](https://smith.langchain.com/) vía su API. Funciona con [Meltano](https://meltano.com/) y cualquier orquestador Singer.

- Replicación **incremental** por `start_time`.
- Primary key `id` (apto para `target-postgres` con `load_method: upsert` y similares).
- Soporta filtros custom y LangSmith self-hosted.

## Requisitos

- Python 3.9+
- [LangSmith API key](https://smith.langchain.com/settings/api-keys)
- `session_id` del project en LangSmith (ver abajo cómo obtenerlo)

## Instalación

```bash
pip install git+https://github.com/fkmurphy/tap-langsmith.git
```

Con Meltano:

```bash
meltano add extractor tap-langsmith --custom \
  --pip_url="git+https://github.com/fkmurphy/tap-langsmith.git@main" \
  --executable=tap-langsmith
```

## Cómo obtener las credenciales

**API key:** [smith.langchain.com/settings/api-keys](https://smith.langchain.com/settings/api-keys) → *Create API Key*. Formato `lsv2_pt_...`.

**Session ID:** entrá al project en LangSmith. El UUID aparece en la URL después de `/projects/p/`. También se puede listar vía API:

```bash
curl -H "X-Api-Key: $LANGSMITH_API_KEY" \
  https://api.smith.langchain.com/api/v1/sessions
```

## Configuración

| Setting | Tipo | Default | Descripción |
|---|---|---|---|
| `api_key` | string | — | **Requerido.** LangSmith API key. |
| `session_id` | string | — | **Requerido.** UUID del project. |
| `start_time` | string | — | ISO 8601 inicial cuando no hay state. Si se omite, usa `lookback_hours`. |
| `api_url` | string | `https://api.smith.langchain.com` | URL base. Cambialo para LangSmith self-hosted. |
| `is_root_only` | bool | `true` | Si `true`, extrae solo runs raíz (`eq(is_root, true)`). Ignorado cuando `filter` está seteado. |
| `filter` | string | — | Expression de filtro custom de LangSmith. Reemplaza el filtro default; el bookmark se agrega automáticamente. |
| `lookback_hours` | int | `36` | Horas hacia atrás en la primera corrida cuando no hay state ni `start_time`. |
| `request_delay_seconds` | number | `10` | Pausa entre páginas para no saturar la API. `0` lo desactiva. |
| `page_size` | int | `80` | Registros por página. |

## Quickstart con Meltano

```bash
meltano init my_pipeline && cd my_pipeline
```

Editá `meltano.yml`:

```yaml
plugins:
  extractors:
  - name: tap-langsmith
    namespace: tap_langsmith
    pip_url: git+https://github.com/fkmurphy/tap-langsmith.git@main
    executable: tap-langsmith
    config:
      api_key: $LANGSMITH_API_KEY
      session_id: $LANGSMITH_SESSION_ID
  loaders:
  - name: target-jsonl
    variant: andyh1203
    pip_url: target-jsonl
```

`.env`:

```
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_SESSION_ID=...
```

Correr:

```bash
meltano install
meltano run tap-langsmith target-jsonl
```

## Producción: Postgres con upsert

```yaml
loaders:
- name: target-postgres
  variant: meltanolabs
  pip_url: meltanolabs-target-postgres
  config:
    host: ...
    port: 5432
    user: ...
    password: $POSTGRES_PASSWORD
    database: ...
    schema: tap_langsmith
    load_method: upsert    # ← clave: evita duplicados en cargas incrementales
```

El tap declara `primary_keys = ["id"]`, así que `target-postgres` crea la PK en la primera carga y hace `ON CONFLICT (id) DO UPDATE` en las siguientes.

## Ejemplos de configuración

### LangSmith self-hosted

```yaml
config:
  api_key: $LANGSMITH_API_KEY
  session_id: $LANGSMITH_SESSION_ID
  api_url: https://langsmith.internal.example.com
```

### Extraer también runs no-raíz (LLM individual, tool calls)

```yaml
config:
  api_key: $LANGSMITH_API_KEY
  session_id: $LANGSMITH_SESSION_ID
  is_root_only: false
```

### Filtro custom

```yaml
config:
  api_key: $LANGSMITH_API_KEY
  session_id: $LANGSMITH_SESSION_ID
  filter: 'eq(status, "error")'   # solo runs con error
```

### Backfill grande

```yaml
config:
  api_key: $LANGSMITH_API_KEY
  session_id: $LANGSMITH_SESSION_ID
  start_time: "2024-01-01T00:00:00Z"
  request_delay_seconds: 2     # acelerar la carga inicial
  page_size: 200
```

## Stream

- **`replication_method`**: `INCREMENTAL`
- **`replication_key`**: `start_time`
- **`primary_keys`**: `["id"]`

### Columnas principales

| Columna | Tipo | Notas |
|---|---|---|
| `id` | string | PK |
| `trace_id` | string | ID de la traza |
| `name` | string | Nombre del run (ej. `AzureChatOpenAI`) |
| `run_type` | string | `chain`, `llm`, etc. |
| `status` | string | `success`, `error`, `pending` |
| `error` | string | Stack/mensaje si `status='error'` |
| `start_time` / `end_time` | datetime | Inicio/fin del run |
| `first_token_time` | datetime | TTFT en runs LLM |
| `inputs` / `outputs` | object | Payloads JSON |
| `extra` | object | Metadata custom |
| `tags` | array | Tags del run |
| `total_tokens`, `prompt_tokens`, `completion_tokens` | number | Tokens |
| `total_cost`, `prompt_cost`, `completion_cost` | number | Costo USD |
| `price_model_id` | string | UUID del modelo |
| `parent_run_id`, `child_run_ids` | string / array | Jerarquía |
| `thread_id`, `session_id` | string | IDs de conversación / project |
| `feedback_stats` | object | Stats agregadas de feedback |

Ver `tap_langsmith/tap.py` para el schema completo.

## Troubleshooting

**`duplicate key value violates unique constraint`** en target-postgres
La tabla existente no tiene PK en `id` y el target no está en `upsert`. Setear `load_method: upsert` y, sobre la tabla existente, deduplicar y crear la PK:

```sql
DELETE FROM tap_langsmith.langsmith
WHERE ctid NOT IN (SELECT MAX(ctid) FROM tap_langsmith.langsmith GROUP BY id);

ALTER TABLE tap_langsmith.langsmith ADD PRIMARY KEY (id);
```

**El sync trae demasiados runs en cada corrida**
Probablemente el state se reseteó. Mirá el log de `Initial bookmark for this run` — si arranca desde el principio, setear un state razonable:

```bash
meltano state set <state_id> '{"singer_state":{"bookmarks":{"tap-langsmith":{"replication_key":"start_time","replication_key_value":"2026-01-01T00:00:00"}}}}'
```

**429 Rate limit**
Subir `request_delay_seconds` (default 10) o pedir una API key con cuota mayor.

## Licencia

[Apache 2.0](./LICENSE).
