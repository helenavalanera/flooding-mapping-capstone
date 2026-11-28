# Flooding Mapping: documentação técnica final

Autora: Helena de Oliveira Valanera. Projeto final do FTL Brasil 2026 Space Tech Bootcamp. Estado em 27/11/2026. Contato: helena.valanera@gmail.com.

Este documento registra a arquitetura, as camadas, as fontes, a publicação e as limitações do Flooding Mapping, e separa com franqueza o que foi **realizado e verificado**, o que ficou **em espera**, e o que **não deu certo ou não foi possível**. Os números vêm dos relatórios do projeto (`reports/qa/`, `docs/`); nenhum foi digitado à mão para este texto.

## 1. Resumo

O Flooding Mapping é um estudo geoespacial de **escoamento superficial potencial** nas ruas de Porto Alegre. Dada uma chuva de referência, estima por trecho viário quanta água as superfícies podem gerar, quanta chega de áreas a montante, onde o terreno tende a reter água e onde existe drenagem cadastrada. O produto é uma landing page científica, um painel com resultados, simulador de cenários (10, 20 e 30 mm) e um mapa interativo em 3D com camadas.

**O que o projeto não é:** não prevê alagamentos, profundidade, extensão nem duração da água; não é serviço em tempo real e não substitui os alertas da Defesa Civil (199). É uma estimativa para apoiar análise e planejamento preventivo.

| Indicador | Valor |
|---|---|
| Trechos de rua analisados (dentro de Porto Alegre) | 143.149 |
| Trechos com depressões no modelo de terreno | 31.545 (cerca de 22%) |
| Trechos em células de 100 m com rede pluvial cadastrada | 70,3% |
| Mediana da contribuição acumulada (dimensão B, a 30 mm) | 49,8 m³ |
| Área classificada com coeficiente de escoamento fundamentado | 17,3% |
| Rede pluvial cadastrada / poços / bocas de lobo | 2.961 km / 88.860 / 44.761 |
| Chuva de referência (30 mm) | percentil 75 dos totais por evento, 2017 a 2026 |
| Testes automatizados na última execução completa | 919 aprovados, 14 pulados, 0 falhas |

## 2. Arquitetura

**Visão geral.** Os dados abertos são processados offline em Python, geram arquivos derivados, e a aplicação (estática, sem servidor próprio) os consome pela rede.

1. **Ingestão e preparação** (`src/flooding_mapping/`): MDE Copernicus GLO-30, malha viária do OpenStreetMap, uso do solo e drenagem da Prefeitura, limites de bairros, série de chuva do Open-Meteo.
2. **Motor determinístico** (`fase3`): V = P × A × C ÷ 1000 por célula de 30 m, em intervalo [C mínimo, C máximo]; a geração é acumulada sobre a sub-árvore a montante de cada célula (massa conservada, erro relativo máximo de 1,4 × 10⁻¹⁴) e amostrada ao longo de cada trecho a cada 6 m. Resultado: contribuição acumulada (não é vazão e não se soma entre trechos).
3. **Camadas derivadas** (Parquets, tiles e fragmentos): escoamento por trecho, drenagem, mapa-base de Porto Alegre em PMTiles, camada GeoAI.
4. **Aplicação estática** (`src/flooding_mapping/app/`, gerada por `python -m flooding_mapping.app.build`): landing (`inicio/`), painel com abas Resultados, Mapa, Simulador e Proveniência, PWA com service worker. O mapa usa MapLibre (WebGL, 3D) com PMTiles lidos por faixas de bytes e cache do navegador; sem WebGL cai em um mapa 2D (Leaflet).
5. **Hospedagem:** aplicação no Cloudflare Pages (`https://flooding-mapping-capstone.pages.dev`), integrada ao GitHub; dados derivados no Cloudflare R2, com URL pública `r2.dev`, prefixos versionados por hash de conteúdo, gzip pré-comprimido e `Cache-Control: immutable`.
6. **Integridade:** o build lê `config/publicacao.json` (versão, URL do R2, camadas publicadas), injeta URLs e SHA-256 dos metadados em `config-dados.js` e a origem do R2 na política de conteúdo (CSP) apenas em `connect-src` e `img-src`. A página recusa um `meta.json` cujo hash não confira.

**Decisões técnicas e alternativas.** (a) Aplicação estática em vez de servidor: custo zero de operação, publicação simples, sem dados pessoais. (b) PMTiles no R2 em vez de um servidor de tiles: o mapa-base inteiro é um arquivo lido por faixas. (c) Motor determinístico e auditável em vez de modelo de aprendizado de máquina: cada número é rastreável a fórmula, unidade e fonte; o aprendizado de máquina ficou restrito à camada experimental. (d) Cenários de 10, 20 e 30 mm em vez de previsão: não há eventos datados com chuva associada para calibrar um modelo.

## 3. Camadas do mapa

| Camada | O que mostra | Estado |
|---|---|---|
| A. Superfícies construídas e pavimentadas | Geração potencial de escoamento onde há edificação e via pavimentada (Método 1) | Realizada |
| B. Contribuição acumulada | Água potencial que chega ao trecho, de montante, por pacote de coeficientes | Realizada |
| C. Retenção topográfica | Altura de preenchimento de depressões no modelo de 30 m (não é profundidade da água) | Realizada |
| D. Drenagem cadastrada | Rede, poços e bocas de lobo do cadastro municipal, como contexto | Realizada |
| E. Fração construída estimada (GeoAI) | Estimativa por célula de 30 m, a partir de imagens de satélite; experimental | Realizada e publicada em prefixo próprio |

As camadas A a D podem se sobrepor e não formam índice composto nem ranking de risco. A camada E é independente do motor e não entra em nenhum número do estudo.

**Recorte municipal.** A malha de ruas do mapa traz 176.836 trechos de uma caixa em volta do município; 143.149 estão dentro de Porto Alegre e 33.687 são de cidades vizinhas. Todos os números do estudo valem para os 143.149. O mapa sombreia a área fora de Porto Alegre e avisa no clique (limite em `static/data/limite_poa.json`).

## 4. Fontes de dados

| Fonte | Uso |
|---|---|
| Copernicus DEM GLO-30 | Elevação de 30 m usada nos cálculos |
| AWS Terrain Tiles | Relevo exibido no mapa (não entra nos cálculos) |
| Prefeitura de Porto Alegre e Profill | Uso e ocupação do solo, cadastro de drenagem pluvial, bairros, marcos e alagamentos de 2013 e 2014 |
| OpenStreetMap e Protomaps | Malha viária e mapa-base |
| Open-Meteo (reanálise ERA5) | Série diária de chuva 2017–2026 (3.593 dias, 618 eventos); estimativa modelada, não pluviômetro |
| Sentinel-2 L2A e AlphaEarth | Somente nos experimentos de GeoAI |
| Serviço Geológico do Brasil | Risco mapeado, como contexto qualitativo |

A referência de coeficientes (Método 1) vem de manual publicado (Texas Department of Transportation); o restante da área usa hipóteses declaradas ou limites físicos. As referências completas estão em `docs/referencias_bibliograficas.md`.

## 5. Camada GeoAI (E)

Um Random Forest sobre Sentinel-2 L2A (2019 a 2021) estima a fração construída por célula de 30 m, usando a Profill como rótulo e referência. Validação espacial por blocos contra a Profill: erro absoluto médio de 0,049 (P1) e 0,052 (quadrante fora de treino). O modelo de fundação AlphaEarth não trouxe ganho; o Prithvi foi documentado e não executado.

A camada foi preparada com imagem WebP em Web Mercator (5 classes de 0,2, transparente fora de Porto Alegre) e publicada em um **prefixo próprio** do R2 (`geoai-f11490d2ef1a`, 2 objetos, 83 KB), sem alterar a versão principal dos dados. Conferências feitas: a imagem cobre o raster de origem e cabe na caixa do mapa-base; a classe de 3.000 pixels sorteados confere com a célula de origem (menos de 2% de discordância); contra o OpenStreetMap, a fração média é 0,014 sobre a água e 0,246 fora dela, e a correlação com as edificações do OSM é máxima sem deslocamento.

**Como interpretar:** é uma estimativa da fração da célula ocupada por construção. Não é impermeabilidade medida, coeficiente de escoamento, risco nem previsão de alagamento.

## 6. Publicação e operação

| Item | Estado em 27/11/2026 |
|---|---|
| Versão principal no R2 | `d-b7f6f03555d9`: 5.596 objetos (35,1 MB), verificada pela URL pública: conteúdo de todos os objetos, PMTiles inteiro (6,9 MB, SHA-256 igual ao manifesto), Range 206, CORS, gzip, cabeçalhos de cache |
| GeoAI no R2 | prefixo `geoai-f11490d2ef1a`, verificado (6 testes, 0 reprovados); ligada em `config/publicacao.json` |
| Aplicação (Pages) | build de produção gerado e testado; **o site publicado só passa a usar o R2 e a GeoAI depois do deploy** |
| Verificação | `tools/verificar_publicacao.py` (somente GET, HEAD e OPTIONS, sem credenciais) |
| Integração contínua | fluxos `publicar-site` e `coletor-crbm` no GitHub Actions; o fluxo de publicação está pronto |
| Controle de versão | Git, ramo `develop` para integração, ramo `main` apenas com o commit inicial; commits em português |

**Comandos.** Build: `PYTHONPATH=src .venv/bin/python -m flooding_mapping.app.build --out dist`. Verificação: `python tools/verificar_publicacao.py https://pub-66f5a12eb6834ef2b736fc85c89ca28c.r2.dev` e, para a GeoAI, `--geoai-prefixo geoai-f11490d2ef1a`. Envio de uma nova versão: `tools/enviar_para_r2.py <pasta> --enviar` com as variáveis `R2_*` no terminal. Detalhes em `docs/publicacao.md`, `docs/r2_cache.md` e `docs/geoai_camada_e.md`.

## 7. Qualidade e verificação

- Suíte automatizada: 919 testes aprovados, 14 pulados (dependem de dispositivo ou credencial), 0 falhas, incluindo testes de navegador em desktop e celular, com e sem WebGL.
- O motor tem verificações de conservação de massa, equivalência com a acumulação de fluxo da biblioteca de suscetibilidade e consistência entre mapa, resultados e Parquet. Cada achado exibido traz uma condição calculada; se ela deixar de valer, o título muda para uma formulação neutra.
- Produção contra o R2 real: teste de navegador com 73 requisições ao R2, 22 de faixas de PMTiles em 206, tiles com gzip, sem violação de CSP, sem erro de JavaScript; filtros (chuva, pacote, limite, dimensão) atualizam o desenho e os resultados.
- Teste de cache: na segunda visita o mapa não faz nenhuma requisição de rede para tiles já vistos.

## 8. O que ficou em espera

1. **Versão `d-e1d18d36ad42` dos dados.** Tem os tiles já recortados em Porto Alegre (143.149 trechos). Não foi enviada ao R2 por decisão de manter a versão publicada. Consequência: o mapa publicado traz a malha de 176.836 trechos e compensa com o sombreamento fora de Porto Alegre. A migração exige enviar 4.923 objetos e criar o manifesto da nova versão.
2. **Cache de borda (CDN).** O endereço `r2.dev` não passa pelas regras de cache da Cloudflare e tem limite de taxa (respostas 403 transitórias em varreduras intensas). Para cache de borda é preciso um domínio próprio ligado ao bucket, com regra de cache; fica para depois.
3. **Deploy do Pages.** O build de produção está pronto; falta o deploy autorizado.
4. **Regularização documental dos dados municipais.** Conduzida à parte pela autora; este projeto não faz conclusão jurídica. Há autorização de uso e de publicação de derivados, com atribuição, de 27/11/2026 (`docs/base_legal_dados.md`).
5. **Validação em dispositivo móvel físico.** Não executada (roteiro em `docs/qa_mobile_fisico.md`); o celular foi testado em emulação de navegador.
6. **Auditoria de acessibilidade automática (por exemplo axe) e leitor de tela.** Não executadas; foram aplicadas áreas de toque de 44 a 48 px, texto além da cor, `aria-label`s e `prefers-reduced-motion`. A conformidade WCAG 2.2 AA não foi comprovada.
7. **Frente estadual e previsão de 72 h.** Pesquisada e arquivada; o produto ativo é municipal. O coletor de ocorrências e a regra de chuva relativa existem, mas dependem de procedimento humano e credenciais, e não fazem parte do produto publicado.
8. **Domínio próprio e conta de organização.** Não contratados.

## 9. O que não deu certo ou não foi possível

1. **Validação preditiva do motor.** Os 124 trechos alagados de 2013 e 2014 não têm horário nem chuva associada, e o motor é condicionado à chuva. A comparação é exploratória: nenhum modelo superou a regra de terreno em uso. Não há validação hidrológica com chuva e nível observados, e o coeficiente C não foi calibrado.
2. **Aprendizado de máquina como gatilho.** O gatilho municipal por aprendizado de máquina não passou no portão de aceite (três critérios independentes, medidos antes do teste); o gatilho em uso é a regra de chuva relativa em 3 dias, calibrada. O modelo ficou registrado como experimental.
3. **GeoAI: ganho sobre a referência.** Não foi possível medir ganho sobre a Profill, porque ela é o rótulo e a referência ao mesmo tempo (interpretação de ortoimagem de 30 cm, mais fina que qualquer imagem pública de 10 m). O AlphaEarth empatou sem ganho; o Prithvi não foi executado (exige HLS com login Earthdata, pesos e dependências pesadas). A hipótese de estimar fração construída onde não há mapeamento fino não foi testada. Não houve validação independente com interpretação manual de ortoimagem licenciada.
4. **Achado de qualidade nas imagens.** Os metadados STAC das 30 cenas Sentinel-2 declaram um deslocamento radiométrico que os números digitais não contêm; foi tratado e documentado, mas é uma limitação das entradas.
5. **Chuva.** É de reanálise, com resolução de grade que suaviza extremos locais; o endpoint de "previsão histórica" do Open-Meteo devolve a mesma série; previsões reais arquivadas existem só desde meados de 2024. Os cenários são uniformes no espaço e no tempo.
6. **Relevo.** O modelo de 30 m não resolve depressões de rua; só uma minoria dos trechos tem depressão a preencher. O MDT municipal de 1 m existe, mas a licença não está confirmada e a exatidão vertical é maior que a profundidade das depressões.
7. **Teste do site publicado com a CSP real no R2 real.** A CSP foi conferida em simulação com o `_headers` verdadeiro e o R2 real foi testado no navegador sem o `_headers`; o teste combinado só ocorre depois do deploy.
8. **Documentos revisados visualmente.** Os arquivos Word e os slides não foram abertos em Word e PowerPoint nesta rodada; a conferência foi por biblioteca.

## 10. Limitações de interpretação

- Contribuição acumulada **não é vazão** e não se soma entre trechos (as áreas a montante se sobrepõem).
- O coeficiente fundamentado cobre 17,3% da área classificada; o restante é cenário declarado. O resultado é um limite superior: sem infiltração, perdas, evaporação nem tempo.
- A relação entre contribuição e presença de drenagem cadastrada reflete, em boa parte, onde há cadastro; não informa capacidade, funcionamento, conectividade nem eficiência.
- Resultados por bairro usam o ponto médio do trecho; trecho sem dado fica "sem dado", nunca zero.
- A camada E mede concordância com a Profill em blocos não vistos, não exatidão contra a verdade de campo.

## 11. Próximos passos recomendados

1. Autorizar o deploy do Pages e repetir o verificador e o teste de navegador contra o site publicado.
2. Enviar a versão `d-e1d18d36ad42` (tiles recortados), criar o manifesto e migrar `config/publicacao.json`.
3. Ligar um domínio próprio ao bucket com regra de cache e repetir a medição de cache de borda.
4. Validar o produto em celular físico e rodar uma auditoria de acessibilidade.
5. Obter eventos datados de alagamento com chuva associada, e capacidade e conectividade da drenagem, para uma validação hidrológica.
6. Obter ortoimagem licenciada para a validação independente da camada GeoAI.
