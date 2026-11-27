# R2, cache HTTP e CDN: preparação dos dados para a publicação

Registro de 27/11/2026. Nada aqui envia dados nem pede credenciais: o que está pronto é a **preparação em disco** e a conferência. O envio e a validação em produção dependem das credenciais da Cloudflare (pendência listada no fim).

## O que as medições mostraram
| Gargalo do mapa interativo | Antes | Depois |
|---|---|---|
| JavaScript baixado na aba Resultados (MapLibre, Leaflet, PMTiles) | 489 KB, 16 arquivos | 141 KB, 13 arquivos: as bibliotecas só vêm ao abrir o mapa (`carregar-mapa.js`) |
| Tiles de relevo à AWS ao abrir o mapa | 153 pedidos, 4,3 MB | cerca de 90 pedidos (zoom máximo do relevo de 14 para 12; o dado é de 30 m) |
| Tiles de escoamento na primeira vista (z13) | 33 tiles, 7,0 MB sem compressão | os mesmos tiles saem com gzip, cerca de 3,7 vezes menores (1,9 MB) |
| Mapa-base no R2 | `rs.pmtiles` do estado, 217 MB | `poa.pmtiles` do município, 6,6 MB (23 pedidos Range e 680 KB lidos na abertura, contra 41 e 940 KB) |
| Acervo a enviar ao R2 | 145 MB de derivados mais 217 MB do mapa-base | 35 MB no total, com gzip nos tiles e o recorte do mapa-base |

(As medições completas, com rede limitada, estão no relatório da rodada de correções.)

## Preparar os objetos
```
PYTHONPATH=src .venv/bin/python tools/preparar_para_r2.py --mapa-poa
```
Escreve `data/interim/r2_preparado/d-<hash>/` (fora do Git) com `fase3/`, `drenagem/` e `mapa/poa.pmtiles`, mais `cabecalhos.json`, que lista, por objeto, `content_type`, `content_encoding`, `cache_control`, tamanho e SHA-256 do conteúdo original. O `d-<hash>` vem de `tools/gerar_manifesto_publicacao.py` e muda quando qualquer arquivo muda, por isso os objetos podem ser `immutable`.

| Objeto | Content-Type | Content-Encoding | Cache-Control |
|---|---|---|---|
| `fase3/tiles/*.pbf`, `drenagem/tiles/*.pbf` | `application/x-protobuf` | `gzip` (já gravado comprimido) | `public, max-age=31536000, immutable` |
| `*/detalhe/*.json` | `application/json` | `gzip` | `public, max-age=31536000, immutable` |
| `*/meta.json` | `application/json` | `gzip` | `public, max-age=300, must-revalidate` (decide qual versão vale; `config-dados.js` ainda confere o hash) |
| `mapa/poa.pmtiles` | `application/octet-stream` | nenhuma (o PMTiles já comprime os tiles por dentro e é lido por faixas de bytes) | `public, max-age=31536000, immutable` |

## Envio (comandos de modelo, sem segredos)
Use as credenciais do R2 no seu ambiente, sem colá-las em chats nem em arquivos do repositório. Com o `wrangler` autenticado, cada objeto leva os cabeçalhos do `cabecalhos.json`, por exemplo:
```
wrangler r2 object put NOME-DO-BUCKET/d-<hash>/fase3/tiles/13/2930/4813.pbf --file ... --content-type application/x-protobuf --content-encoding gzip --cache-control "public, max-age=31536000, immutable"
```
Com 5,6 mil objetos, prefira a API compatível com S3 (`aws s3 sync --content-encoding gzip` por tipo, ou `rclone`) e confira ao fim: contagem, tamanhos e, por amostragem, o SHA-256 do conteúdo descomprimido contra `sha256_do_original`.

## Domínio, CORS e CSP
- **Domínio próprio no bucket** (`dados.seu-dominio`): só nele valem o cache da Cloudflare e as regras de cache; `r2.dev` serve para teste, não para produção.
- **CORS do bucket**, com a origem do site (`https://seu-dominio`): métodos `GET` e `HEAD`; cabeçalhos permitidos `Range`, `If-None-Match`; cabeçalhos expostos `Content-Range`, `Content-Length`, `ETag`, `Accept-Ranges`; `MaxAgeSeconds` de 86400.
- **Regra de cache da Cloudflare** para o domínio dos dados: *Eligible for cache*, *Edge TTL* respeitando a origem. O PMTiles (arquivo único lido por faixas) só se beneficia do cache de borda se a regra o tornar elegível; confira com `cf-cache-status` em duas leituras seguidas.
- **CSP**: `python -m flooding_mapping.app.build --out dist --r2-origem https://dados.seu-dominio` acrescenta a origem a `connect-src` e `img-src` no `_headers`.
- **config-dados.js**: `fase3`, `drenagem` e `mapa` com a URL `https://dados.seu-dominio/d-<hash>/...`, `versao` e `meta_sha256` do manifesto. Com `fase3` absoluta, `tools/gerar_landing.py` volta a prometer as camadas trecho a trecho na landing.

## Validar o Range e a compressão (depois do envio)
```
curl -sI -H "Range: bytes=0-16383" https://dados.seu-dominio/d-<hash>/mapa/poa.pmtiles      # espera 206, Content-Range, Accept-Ranges: bytes e CORS
curl -sI -H "Accept-Encoding: gzip" https://dados.seu-dominio/d-<hash>/fase3/tiles/13/2930/4813.pbf   # espera Content-Encoding: gzip e Cache-Control immutable
```
E `tests/e2e/estatico.js` (topologia Pages mais bucket) contra as URLs reais.

## Cache no site (Pages)
`_headers` (gerado por `build.py`): HTML, JS e CSS seguem a revalidação padrão do Pages (uma publicação vale na hora); `/vendor/*` e `/icone-*` ficam um dia; `/inicio/img/*` (os quatro mapas WebP) e `/data/*` ficam uma hora com `stale-while-revalidate` de um dia.

## Carregamento progressivo
Os tiles de escoamento existem só nos zooms 13 a 15 (abaixo disso passam de 1,9 MB e perdem trechos curtos), então a camada só é pedida de perto; o detalhe de cada trecho vem em fragmentos sob demanda; o relevo e o mapa-base são lidos por faixas. As bibliotecas do mapa só carregam ao abrir a aba Mapa. **Pendente:** regenerar os tiles de escoamento sem as vias de fora do município (19% dos trechos), que reduz o peso na mesma proporção.
