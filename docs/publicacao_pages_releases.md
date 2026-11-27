# Arquitetura de publicação: GitHub Pages, Releases e distribuição de dados

Estado: **planejamento e preparação local. Nada foi publicado**: nenhum repositório, release, bucket, tag, push ou deploy foi criado ou executado.
Este documento complementa [`publicacao.md`](publicacao.md) (workflow do site estadual já desenhado), [`hospedagem.md`](hospedagem.md) e [`render.md`](render.md) (servidor com API).

## 1. O que precisa ser publicado

| Parte | Tamanho medido | Arquivos | Muda quando |
|---|---|---|---|
| Interface (HTML, JS, CSS, landing, PWA, `data/*.json`) | 7,4 MB | dezenas | a cada alteração de código |
| Camada de escoamento (`fase3/`: tiles MVT + fragmentos + `meta.json`) | 69,7 MB | 2.059 | quando o motor da Fase 3 é reexecutado |
| Camada de drenagem (`drenagem/`) | 68,6 MB | 3.536 | quando o inventário é reprocessado |
| Mapa-base `rs.pmtiles` (lido por faixas de bytes) | 216,7 MB | 1 | raramente |
| Parquets de origem (`data/processed/fase3/*.parquet`) | não publicados | 4 | só auditoria; o hash fica em `meta.json` |

Total servido pelo navegador: cerca de 362 MB. As partes dinâmicas (`/api/risco`, ocorrências, rotas, previsão) exigem o servidor Python e **não existem em hospedagem estática**: numa publicação só estática, as abas Resultados, Simulador, Mapa (escoamento e drenagem) e a landing funcionam; Mobilidade, Ocorrências e a previsão horária ficam indisponíveis e a tela já diz isso (ver `docs/mapa_simulador_pwa.md`).

## 2. Limites oficiais consultados em 26/11/2026

| Serviço | Limite ou preço | Fonte |
|---|---|---|
| GitHub Pages | site publicado até **1 GB**; repositório-fonte com limite *recomendado* de 1 GB; banda *soft* de **100 GB/mês**; 10 builds/hora (*soft*, não vale para workflow próprio); implantação expira em **10 min**; não é para hospedar negócio comercial | docs.github.com, "GitHub Pages limits" |
| GitHub Releases | até 1.000 arquivos por release; cada arquivo **abaixo de 2 GiB**; sem limite de tamanho total nem de banda | docs.github.com, "About releases" |
| Cloudflare R2 (Standard) | gratuito por mês: 10 GB-mês, 1 milhão de operações Classe A, 10 milhões Classe B; depois US$ 0,015/GB-mês, US$ 4,50 por milhão (A), US$ 0,36 por milhão (B); **sem cobrança de saída** | developers.cloudflare.com/r2/pricing |

Fontes adicionais lidas em 26/11/2026 (páginas oficiais da Cloudflare, com data de modificação no próprio site):

| Fato | Fonte |
|---|---|
| CORS do R2 é uma política JSON no bucket (origens, métodos, cabeçalhos permitidos, cabeçalhos expostos, `MaxAgeSeconds`); domínios próprios ligados ao bucket devolvem os cabeçalhos CORS automaticamente; objetos em cache precisam de purga após mudar a política. A página **não cita** `Range` nem diz que o CORS vale no `r2.dev` | developers.cloudflare.com/r2/buckets/cors/ (modificada em 23/09/2026) |
| `r2.dev` é "para uso fora de produção" e tem limite de taxa; cache da Cloudflare, WAF e controles de acesso só valem em domínio próprio. A página **não declara** suporte a `Range` nem `Cache-Control` | developers.cloudflare.com/r2/buckets/public-buckets/ (12/11/2026) |
| Preços e faixa gratuita do R2 (acima); a faixa gratuita vale só para armazenamento Standard; saída direta do R2, inclusive por `r2.dev`, é gratuita | developers.cloudflare.com/r2/pricing/ (30/10/2026) |
| Pages: 1 GB publicado, 100 GB/mês (*soft*), 10 min de implantação, não é para negócio comercial; a própria página sugere CDN ou Releases como alternativa | docs.github.com, "GitHub Pages limits" |
| Releases: até 1.000 arquivos por release, cada um abaixo de 2 GiB, sem limite de tamanho total nem de banda. Nada sobre CORS | docs.github.com, "About releases" |

### Medições feitas em 26/11/2026 (somente leitura, endpoints públicos de terceiros, sem criar nada)

O projeto **não tem** endpoint de Pages, Release ou bucket próprio publicado; por isso estas medições mostram o comportamento da plataforma, não a validação da hospedagem do projeto.

| Teste (`curl -I`, com `Origin: https://exemplo.invalid`) | Resultado |
|---|---|
| Página servida pelo GitHub Pages (`pages.github.com`) | `access-control-allow-origin: *`, `cache-control: max-age=600`, `accept-ranges: bytes` |
| Asset de Release público (`github.com/cli/cli/releases/download/...`) | resposta **302** sem `Access-Control-Allow-Origin`, `cache-control: no-cache`; destino `release-assets.githubusercontent.com` (domínio diferente, URL assinada com validade de cerca de 1 hora); o arquivo final vem do armazenamento Azure com `accept-ranges: bytes` e **sem** cabeçalho CORS |

Leitura: um navegador que fizer `fetch` entre origens para um asset de Release recebe um redirecionamento sem CORS e **bloqueia a leitura**. Isto vale para os cabeçalhos observados nesse asset; só um release do próprio projeto confirma. Já o Pages devolve `*`, de modo que o site estático pode ser lido por outra origem, e o cache padrão é de 10 minutos (não configurável: o Pages não permite definir cabeçalhos; a documentação oficial lida não declara nem CORS nem `Cache-Control`).

**Continua não verificado:** CORS e `Range` do R2 (a documentação não os declara; só um bucket de teste responde), o prazo de 10 min do Pages com 362 MB e o comportamento do `Range` do mapa-base no Pages.

## 3. Alternativas comparadas

Duas arquiteturas, definidas pela origem dos dados (a interface fica no Pages nas duas):

- **Pages + Releases.** Só funciona de duas maneiras: (a) o navegador lê os assets direto do Release (origem diferente; **bloqueado pela falta de CORS medida acima**) ou (b) o fluxo de publicação baixa o Release e o inclui no artefato do Pages (mesma origem, sem CORS, mas os dados voltam a contar nos limites do Pages).
- **Pages + R2.** A interface lê os tiles e fragmentos de um bucket por URL configurável (`config-dados.js`), com CORS configurado no bucket.

| Critério | Pages + Releases | Pages + R2 |
|---|---|---|
| Custo | Zero. Sem limite de banda declarado nos Releases; o Pages tem banda *soft* de 100 GB/mês | Dentro da faixa gratuita nas premissas da seção 7 (US$ 0 por mês); acima dela, US$ 0,015/GB-mês e US$ 0,36 por milhão de leituras; saída gratuita |
| CORS | Releases: **sem CORS no asset medido** (302 sem `Access-Control-Allow-Origin`), logo (a) não serve. Com (b) não há CORS a configurar. Pages: `*` | Configurável no bucket; funciona em domínio próprio. A documentação não cita `Range` nem confirma CORS no `r2.dev`: **a validar** |
| Distribuição de tiles | Inadequada em (a): redirecionamento para URL assinada de 1 hora, uma por arquivo, sem cache longo (`no-cache`). Em (b) os 5.600 arquivos viajam no Pages | Adequada: objetos pequenos por URL estável. Cache da Cloudflare só em domínio próprio; `r2.dev` é "para uso fora de produção" e limitado por taxa |
| Versionamento | Um release imutável por versão, com manifesto e hash | Prefixo `d-<hash>/` por versão no bucket, com o mesmo manifesto |
| Cache | Pages: `max-age=600`, fixo. Release: `no-cache` na resposta inicial | Controlável (`Cache-Control` do objeto e regras no domínio próprio), a confirmar em teste |
| Desempenho | Pages atrás de CDN; Release exige um redirecionamento a cada arquivo | CDN da Cloudflare em domínio próprio; sem medição do projeto |
| Manutenção | Baixa: tudo no GitHub, fluxo de CI único | Média: conta, bucket, CORS, domínio e credenciais de escrita no CI |
| Dependência de fornecedor | Só o GitHub | GitHub e Cloudflare (o projeto já usa R2 para modelo e coletor) |
| Complexidade operacional | (b): um passo extra de CI e o prazo de 10 min do Pages; (a): inviável | CORS, domínio e CSP (`connect-src`) a ampliar; rollback é trocar a base em `config-dados.js` |
| Limite que pesa | 1 GB e 10 min do Pages (362 MB cabem no tamanho; o prazo não foi medido) | Faixa gratuita de operações, não de volume |

**Tamanhos:** os dados servidos somam cerca de 362 MB; o mapa-base (217 MB) é a maior peça.

## 3.1 Recomendação (não executada; decisão da autora)

1. **Para o estágio atual: Pages com os dados no próprio artefato (mesma origem), versionados por release (a variante b).** É a de menor custo e complexidade, não precisa de CORS, e 362 MB ficam abaixo de 1 GB. Releases serve como arquivo imutável de cada versão e fonte do rollback, **não como servidor lido pelo navegador**.
2. **Custo estimado:** zero. Premissas: 20 visitas por dia, 10 MB por visita (6 GB/mês, 6% da banda *soft* do Pages) e quatro atualizações por semestre.
3. **Limitações:** o Pages não permite definir cabeçalhos (cache fixo de 10 min e CSP só por `<meta>`, sem `frame-ancestors`); cada implantação reenvia cerca de 362 MB; não há servidor, então as abas que usam a API ficam indisponíveis; o Pages não é para uso comercial.
4. **Testes que faltam (todos exigem operação remota, só com autorização):** (i) uma implantação de teste para medir o prazo de 10 min com os 362 MB; (ii) `Range` do `rs.pmtiles` servido pelo Pages; (iii) se o mapa-base não couber no prazo, um bucket de teste no R2 com CORS, `Range` e `Cache-Control` medidos antes de qualquer migração; (iv) o console do navegador na URL publicada.
5. **Caminho de evolução:** se o prazo de 10 min ou a banda *soft* virarem problema real, mover primeiro **só o mapa-base** (217 MB, muda raramente) para o R2 com domínio próprio, e depois, se preciso, `fase3/` e `drenagem/`. A troca é só de `config-dados.js`; não há outra arquitetura justificada hoje.

## 4. O que já está pronto no código (local, testado)

1. **Separação interface e dados.** `fase3/` e `drenagem/` são pastas independentes, lidas por `meta.json`, tiles e fragmentos. O servidor local e o build só as montam (`servidor.py`, `build.py --fase3 --drenagem`).
2. **Versão dos dados.** `tools/gerar_manifesto_publicacao.py` lista todos os arquivos servidos com tamanho e SHA-256 e deriva a **versão do conjunto** do conteúdo (`d-<12 hex>`): se qualquer tile mudar, a versão muda. Versão atual: `d-6c3c2b28e0ee` (fase3: 2.059 arquivos; drenagem: 3.536). `--verificar` confere uma cópia contra o manifesto e acusa arquivo adulterado, ausente ou a mais.
3. **Integridade dos Parquets.** `tools/auditar_integridade.py` confere os hashes dos Parquets, a continuidade dos fragmentos, os tiles e a rastreabilidade dos indicadores (19 verificações, 0 falhas em 26/11/2026).
4. **Caminhos configuráveis.** As bases dos dados são lidas de `config-dados.js` (ver `docs/mapa_simulador_pwa.md`): relativas por padrão (funcionam sob `/repositorio/` no Pages) ou absolutas (bucket). Nenhum caminho local é usado pela página.
5. **Falha de dados.** Se `meta.json` não carrega, a camada diz que está indisponível e oferece tentar de novo; a página não mostra dado ausente como zero.

## 5. Estrutura de diretórios publicada

```
/                      index.html, *.js, style.css, sw.js, manifest.webmanifest   (interface)
/inicio/               landing científica e página "no celular"
/pwa/                  app de rotas (usa a API; sem servidor, só o aviso de indisponibilidade)
/data/                 resultados_poa.json, territorios.json, ... (versionados com a interface)
/config-dados.js       URLs-base e versão esperada dos dados (a única peça trocada entre ambientes)
/fase3/  /drenagem/    dados derivados (mesma origem em Pages + Releases (variante b); URL externa em Pages + R2)
/mapa/rs.pmtiles       mapa-base (faixas de bytes; precisa de suporte a Range)
```

Versões dos dados em Pages + Releases: `releases/dados-d-<hash>` com `fase3.tar`, `drenagem.tar` e `manifesto_d-<hash>.json`. Em Pages + R2: `<bucket>/d-<hash>/fase3/...`.

## 6. CORS, cache e CSP

- **Mesma origem (Pages + Releases, variante b):** nada a configurar. `connect-src 'self'` e `img-src 'self'` já bastam.
- **Origem externa (Pages + R2):** o bucket precisa responder `Access-Control-Allow-Origin` para a origem da interface, método `GET` e `HEAD`, e o cabeçalho `Range` (o mapa-base lê por faixas). A CSP da página precisa listar o domínio em `connect-src` (e `img-src`, se houver imagens). O Pages não permite definir cabeçalhos: a CSP da interface estática deve ir como `<meta http-equiv>` (que não aceita `frame-ancestors`; esse ponto da política só vale com servidor próprio).
- **Cache.** Interface e `data/*.json`: revalidar sempre (o Pages envia `max-age` curto). Dados versionados (`fase3/`, `drenagem/`): como o conjunto é imutável por versão, podem ter cache longo **se a URL contiver a versão**; sem versão na URL, mantenha cache curto. O service worker nunca guarda tiles nem fragmentos (política em `sw.js`).

## 7. Estimativa de custo (premissas explícitas)

Premissas: um único conjunto de dados de ~140 MB (mais 217 MB do mapa-base, se também for ao bucket); 20 visitas por dia, cada uma baixando em média 8 MB de tiles e 2 MB de interface; 4 atualizações dos dados por semestre.

- **Pages (com Releases):** banda ≈ 20 × 10 MB × 30 = 6 GB/mês, ou 6% do limite *soft* de 100 GB. Custo: zero.
- **R2:** armazenamento 0,36 GB (dentro dos 10 GB gratuitos); leituras ≈ 20 visitas × 150 arquivos × 30 = 90.000 Classe B por mês (dentro dos 10 milhões gratuitos); escritas por publicação ≈ 5.600 Classe A (dentro de 1 milhão). Saída gratuita. Custo: zero nessas premissas; mesmo 100 vezes mais visitas ficaria na faixa gratuita de operações.
- **Releases:** sem custo nem limite de banda declarado, mas o asset medido não envia CORS: serve como arquivo, não como origem de leitura do navegador.
- **Domínio:** domínio próprio (opcional) é custo à parte, não estimado aqui.

As premissas de tráfego são hipóteses de uso, não medidas. Uma divulgação grande pode ultrapassá-las.

## 8. Checklist de publicação (a executar só com autorização)

1. Regenerar e conferir os dados: `python tools/auditar_integridade.py` (0 falhas).
2. Gerar o manifesto: `python tools/gerar_manifesto_publicacao.py` e registrar a versão `d-<hash>`.
3. Rodar a suíte completa e os e2e.
4. Montar o site localmente: `python -m flooding_mapping.app.build --model ... --card ... --out site --fase3 data/processed/fase3_web --drenagem data/processed/drenagem_web` e conferir `site/` (a suíte falha se houver Parquet, modelo ou credencial na saída).
5. Pages + Releases: criar o release `dados-d-<hash>` com os arquivos dos dados e o manifesto; o workflow baixa, executa `--verificar` e só então monta o artefato do Pages.
6. Pages + R2: enviar a pasta versionada ao bucket, configurar CORS e ampliar a CSP.
7. Ajustar `config-dados.js` (base e `meta_sha256` esperados) e publicar.
8. Abrir a URL publicada, verificar console limpo, o mapa com escoamento e drenagem, o modo sem conexão e a versão exibida no rodapé.

## 9. Procedimento de rollback

1. Identificar a versão anterior `d-<hash>` no manifesto arquivado.
2. Pages + Releases: reimplantar o workflow com o release anterior. Pages + R2: trocar a base em `config-dados.js` para o prefixo anterior e publicar só esse arquivo.
3. Conferir com `--verificar` contra o manifesto anterior e abrir a página: o rodapé deve mostrar a versão anterior.
4. Os dados antigos nunca são sobrescritos: cada versão tem seu release ou prefixo. O service worker troca de versão por nome de cache; o aviso "nova versão" aparece para quem já tinha o app aberto.

## 10. Riscos e limites

- O prazo de 10 minutos do Pages pode estourar com 362 MB; medir antes de contar com Pages incluindo o mapa-base.
- O CORS de Releases foi medido só num asset público de terceiro (sem CORS); falta um release do próprio projeto.
- O mapa-base e a previsão dependem de serviços e arquivos fora do repositório (mapa-base não versionado; Open-Meteo).
- Sem servidor, as abas que usam a API não funcionam; o app de rotas (`/pwa/`) só mostra indisponibilidade.
- O Pages não é para serviço comercial: o projeto é acadêmico e gratuito.
