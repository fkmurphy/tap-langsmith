# tap-langsmith

Singer tap que extrae *runs* (ejecuciones) de [LangSmith](https://smith.langchain.com/) usando su API. Compatible con [Meltano](https://meltano.com/) y cualquier orquestador Singer.

Replicación **incremental** por `start_time`, primary key `id` (apto para `target-postgres` con `load_method: upsert` y similares).

## Requisitos

- Python 3.8+
- Una [LangSmith API key](https://smith.langchain.com/settings/api-keys)
- El `session_id` (UUID del project) que querés extraer

## Instalación

### Con `pip`

```bash
pip install git+https://github.com/fkmurphy/tap-langsmith.git
```

### Con `poetry`

```bash
git clone https://github.com/fkmurphy/tap-langsmith.git
cd tap-langsmith
poetry install
```

## Configuración

| Setting | Tipo | Requerido | Descripción |
|---|---|---|---|
| `api_key` | string | ✅ | LangSmith API key (formato `lsv2_pt_...`). |
| `session_id` | string | ✅ | UUID del project/session en LangSmith. |
| `start_time` | string | ❌ | ISO 8601 (ej. `2025-01-01T00:00:00Z`). Solo se usa cuando no hay bookmark en el state. Si no se setea, lookback default de 36 h. |

### Ejemplo `config.json` (uso standalone)

```json
{
  "api_key": "lsv2_pt_...",
  "session_id": "00000000-0000-0000-0000-000000000000",
  "start_time": "2025-11-01T00:00:00Z"
}
```

### Ejemplo Meltano (`meltano.yml`)

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
      # start_time: 2025-01-01T00:00:00Z   # opcional, sólo primera corrida
```

Y en `.env`:

```
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_SESSION_ID=...
```

## Uso

### CLI directo

```bash
tap-langsmith --config config.json
```

### Con Meltano

```bash
meltano run tap-langsmith target-jsonl       # para probar
meltano run tap-langsmith target-postgres    # producción
```

> **Tip target-postgres**: para evitar duplicados en cargas incrementales, configurá `load_method: upsert` en el loader. Este tap ya declara `primary_keys = ["id"]`, así que `target-postgres` puede hacer `ON CONFLICT (id) DO UPDATE`.

## Stream `tap-langsmith`

Un único stream con replicación incremental.

- **`replication_method`**: `INCREMENTAL`
- **`replication_key`**: `start_time`
- **`primary_keys`**: `["id"]`

### Columnas principales

| Columna | Tipo | Notas |
|---|---|---|
| `id` | string | PK |
| `trace_id` | string | ID de la traza |
| `name` | string | Nombre del run (ej. `LangGraph`, `AzureChatOpenAI`) |
| `run_type` | string | `chain`, `llm`, etc. |
| `status` | string | `success`, `error`, `pending` |
| `error` | string | Mensaje si `status='error'` |
| `start_time` / `end_time` | datetime | Inicio/fin del run |
| `first_token_time` | datetime | Útil para TTFT en runs LLM |
| `inputs` / `outputs` | object | Payloads JSON |
| `extra` | object | Metadata custom del usuario |
| `tags` | array | Tags del run |
| `total_tokens`, `prompt_tokens`, `completion_tokens` | number | Tokens |
| `total_cost`, `prompt_cost`, `completion_cost` | number | Costos USD |
| `price_model_id` | string | UUID del modelo en LangSmith pricing |
| `parent_run_id`, `child_run_ids` | string / array | Jerarquía (al usar `is_root_only=true` parent es null) |
| `thread_id`, `session_id` | string | Identificadores de conversación / project |
| `feedback_stats` | object | Stats de feedback agregadas |
| `events` | array | Eventos del run |

El payload completo de la API se vuelca; ver `tap_langsmith/tap.py` para el schema exhaustivo.

## Comportamiento por defecto

- Solo extrae **runs raíz** (`eq(is_root, true)` en el filter de LangSmith).
- Lookback de **36 h** la primera vez que no hay bookmark en el state.
- Paginación con cursor del lado del servidor; `page_size = 80`.
- Pausa de **10 s** entre páginas para no saturar la API.

## Troubleshooting

**`duplicate key value violates unique constraint`** en target-postgres
Pasa cuando reusás una tabla existente que no tiene la PK definida sobre `id` y el target no está en `upsert`. Soluciones: `load_method: upsert` en el target **y** deduplicar la tabla con `DELETE … WHERE ctid NOT IN (SELECT MAX(ctid) … GROUP BY id)`. Después `ALTER TABLE … ADD PRIMARY KEY (id)`.

**No se sincronizan registros**
Mirá los logs de `_get_initial_bookmark`. Si el state tiene un bookmark muy viejo, va a re-emitir todo desde ahí (upsert evita los duplicados, pero gasta API calls). Reseteá el state con `meltano state set <state_id> ...` si querés acotar.

**Rate limit (429) de LangSmith**
La pausa interna entre páginas evita esto en condiciones normales. Si lo seguís viendo, esperá o usá API keys con mayor cuota.

## Desarrollo

```bash
poetry install
poetry run tap-langsmith --config config.json | head
```

Ver [`CONTRIBUTING.md`](./CONTRIBUTING.md) para guías de PR y proceso.

## Licencia

[Apache 2.0](./LICENSE).
