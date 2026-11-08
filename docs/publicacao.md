# Publicação da interface estadual (GitHub Pages)

A interface é uma página **estática**: o navegador só lê arquivos JSON. Todo o processamento
(previsão de chuva, modelo, casamento dos bloqueios com a malha) roda em um fluxo do GitHub
Actions que monta a pasta `site/` e a publica pelo próprio Pages, **sem fazer commits**
(os commits do repositório continuam todos em seu nome).

```
Open-Meteo (chuva) ─┐
CPRv BM (bloqueios) ─┼─► workflow publicar-site ─► site/ (HTML + JSON) ─► GitHub Pages
modelo no R2 ───────┘      (a cada 3 h)
```

Arquivos: `.github/workflows/publicar-site.yml`, `src/flooding_mapping/app/build.py`,
`src/flooding_mapping/models/publish.py`.

## O que só o dono do repositório pode fazer (uma vez)

1. **Ativar o Pages com origem em Actions.** Settings → Pages → Build and deployment →
   Source: **GitHub Actions**.
2. **Enviar o modelo ao R2.** O artefato não vai para o git (e o cartão em
   `reports/ml/gatilho_estrito.json` registra o hash). No computador onde o modelo foi treinado:

   ```bash
   export R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET=...
   PYTHONPATH=src .venv/bin/python -m flooding_mapping.models.publish upload \
     --model artifacts/models/<versao>/modelo.joblib --card reports/ml/gatilho_estrito.json
   ```

   O envio é recusado se o arquivo não for o que o cartão descreve. Usa 2 operações de escrita
   (Classe A) do R2; cada publicação do site usa 2 de leitura (Classe B), cerca de 480 por mês.
3. **Rodar o workflow uma vez à mão** (Actions → publicar-site → Run workflow) e abrir a URL que
   o passo `publicar` mostra. Depois ele roda sozinho a cada 3 horas.

Os segredos `R2_*` já usados pelo coletor servem aqui. Variável opcional `SITE_ATIVO = false`
pausa a publicação.

## Segurança

- Os segredos existem **somente** no passo que baixa o modelo. O passo que consulta as APIs e
  monta o site roda sem segredo no ambiente.
- O modelo baixado é conferido contra o hash do cartão; o build recusa uma versão diferente da
  documentada.
- O site publicado contém só HTML, JavaScript, CSS e JSON. Um teste (`test_app_build.py`) falha
  se aparecer qualquer padrão de credencial, modelo ou arquivo Parquet na saída.
- O texto livre vindo da CPRv BM é escapado pela página antes de ser exibido.
- Se a CPRv BM não responder, o site é publicado **sem** a camada de bloqueios e avisa.

## Limites

- O `cron` do GitHub pode atrasar; a página mostra a data e a hora da última atualização.
- Repositórios públicos têm o agendamento desativado após 60 dias sem atividade.
- A previsão usa a API gratuita do Open-Meteo (uso não comercial), com cerca de 500 de custo por
  execução, 8 execuções por dia.
- O modelo foi treinado com reanálise e opera com previsão; ver `docs/ml_gatilho.md`.
