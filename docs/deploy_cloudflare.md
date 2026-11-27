# Publicação: Cloudflare Pages (aplicação) e R2 (dados)

O acervo completo, o layout previsto no R2 e a migração controlada estão em [`catalogo_dados.md`](catalogo_dados.md). Armazenar um dado no R2 não o torna público.

Estado em 26/11/2026: **nada foi publicado**. O build está pronto e foi verificado localmente; faltam as credenciais da Cloudflare, que não estão neste ambiente (`wrangler whoami`: não autenticado; nenhuma variável `CLOUDFLARE_*` nem `R2_*`).

## Aplicação (Pages)

```bash
PYTHONPATH=src .venv/bin/python -m flooding_mapping.app.build --out dist        # 54 arquivos, com o _headers, 1,6 MB: landing, painel, simulador, vendor do mapa
CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... npx wrangler pages deploy dist --project-name <projeto> --branch main
```

Token com permissão de edição de Pages. A raiz leva à landing (`inicio/`); o painel é `painel.html`.

O build gera `dist/_headers` com a política de conteúdo do servidor local (`servidor.CSP`, conferida por teste), os cabeçalhos de segurança e o cache de `/vendor/*`. Com a origem pública do R2, rode o build com `--r2-origem https://dados.exemplo.org`: ela entra em `connect-src` e `img-src`; sem isso o navegador bloqueia os dados do bucket. A raiz e o painel podem ser enquadrados pela mesma origem (página "No celular"); o resto, por ninguém. O Pages soma cabeçalhos de regras que casam com a mesma página, por isso essas rotas soltam a política geral (`! Content-Security-Policy`) antes de pôr a sua.

## Dados (R2)

| Objeto | Pode ir? |
|---|---|
| `mapa/rs.pmtiles` (217 MB, OpenStreetMap, ODbL) | Sim, com a atribuição já exibida no mapa |
| `fase3/` (escoamento, derivado da Profill) e `drenagem/` (cadastro) | **Armazenar no R2: sim. Acesso público: só depois de a licença estar registrada e a redistribuição identificada.** Até lá o mapa mostra o relevo e o mapa-base, e as dimensões A a D avisam que faltam dados |

CORS do bucket: origens = a URL do Pages; métodos `GET` e `HEAD`; cabeçalhos permitidos `Range`; expostos `Content-Range`, `Accept-Ranges`, `Content-Length`; `MaxAgeSeconds` alto. O PMTiles é lido por faixas de bytes, então o bucket precisa responder `206`.

Depois de subir: em `dist/config-dados.js`, apontar `mapa` (e, quando liberados, `fase3` e `drenagem`) para as URLs públicas do bucket; `tools/gerar_manifesto_publicacao.py` gera os hashes de `meta_sha256`.

## Backup e automações

- Backup privado no Google Drive: não feito (o inventário e o tamanho dos dados locais, 9 GB, pedem um passo à parte).
- `coletor-crbm.yml` desativado (agendamento removido); `publicar-site.yml` só roda manualmente e exige `SITE_ATIVO = true`. Nenhum dos dois é o caminho do Cloudflare Pages.
