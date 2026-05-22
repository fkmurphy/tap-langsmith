# Contributing

¡Gracias por considerar contribuir a `tap-langsmith`!

## Reportar bugs / pedir features

Abrí un issue en [GitHub](https://github.com/fkmurphy/tap-langsmith/issues) con:

- Versión de `tap-langsmith` (`pip show tap-langsmith` o el `pip_url` que usás).
- Versión de Python y del target (si aplica).
- `meltano.yml` o `config.json` minimizado (sin secretos).
- Logs relevantes (`meltano run … --log-level debug` o `tap-langsmith --config … 2>&1`).
- Pasos para reproducir.

## Desarrollo local

Requisitos: Python 3.8+ y [Poetry](https://python-poetry.org/).

```bash
git clone https://github.com/fkmurphy/tap-langsmith.git
cd tap-langsmith
poetry install
poetry run tap-langsmith --config config.json | head
```

Tu `config.json` local **no debe** commitearse; agregalo a tu `.gitignore` o usá `config.example.json`.

## Pull requests

1. Forkeá y creá una branch descriptiva: `feat/...`, `fix/...`, `docs/...`.
2. Mantené los cambios chicos y enfocados — un PR por intención.
3. Si tocás el schema o el filter de la API:
   - Verificá que sigue compatible con configs existentes (o explicitá el breaking change en el PR description).
   - Probá contra una API key real (al menos un sync chico).
4. **Firmá los commits con GPG/SSH** (`git commit -S`). En GitHub aparece como *Verified*.
5. PR description: qué cambia, por qué, y un test plan corto (incluso si es manual).

## Estilo

- PEP 8. No hay linter forzado todavía, pero no inventes estilos nuevos.
- Cuando agregues un setting al `config_jsonschema`, **mantenelo backwards-compatible** vía default. Setups en producción no deberían romperse al actualizar.

## Releases

Versionado [SemVer](https://semver.org/). El proceso de release todavía es manual:

1. Bumpear `version` en `pyproject.toml`.
2. Tagear `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. (Futuro) Publicar a PyPI vía GitHub Actions.

## Código de conducta

Sé amable. Asumí buena fe. Critica el código, no a la persona.
