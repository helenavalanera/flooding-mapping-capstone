# Flooding Mapping

Projeto para ingestão, validação, preparação e análise de acessibilidade em
eventos de inundação, com cenários e indicadores de robustez reproduzíveis.

## Estrutura

- `config/`: configurações da análise.
- `data/events/`: eventos e cenários versionados.
- `src/flooding_mapping/`: pipeline Python.
- `tests/`: testes automatizados.
- `outputs/`: tabelas e mapas gerados.
- `reports/qa/`: relatórios de qualidade dos dados.

Dados brutos e intermediários não são versionados. Consulte
`data/raw/manifest.json` para registrar suas fontes.

## Uso

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
pytest
```

Os módulos podem ser usados individualmente ou combinados em um pipeline.

