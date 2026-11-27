# Mapa de análise, simulador, PWA e auditoria final (26/11/2026)

> **Atualização da Etapa 3 (26/11/2026):** o PWA (app de rotas do cidadão e aplicação de análise instalável) foi **arquivado** em `src/flooding_mapping/app/arquivo/` como frente futura de monitoramento em tempo real: a aplicação atual não tem manifesto, botão de instalar nem service worker (o painel remove o antigo), e o celular não é mais levado ao app de rotas. As seções 4 e 5 abaixo descrevem o que foi construído e hoje está guardado; o que vale para a aplicação atual está em `app/arquivo/README.md`. O mapa-base passou a ser configurável em `config-dados.js` (`mapa`), e a versão estática tem a landing como entrada (`index.html` → `inicio/`; o painel é `painel.html`).

Nada foi commitado, enviado ou publicado. Esta página registra o que mudou, por quê, como foi testado e o que continua em aberto.

## 1. Auditoria do estado de partida

- Branch `develop`, HEAD `dceb39b`, 154 entradas locais no início (nenhuma descartada).
- Mapa: MapLibre 3D com fallback Leaflet; camadas de escoamento (Fase 3) e de drenagem já carregadas sob demanda a partir de `fase3/` e `drenagem/`; consulta de trecho por fragmento; legendas calculadas dos `meta.json`.
- O que já atendia e foi **preservado**: os controles de pacote, limite e chuva, o painel do trecho, as legendas, o carregamento tardio, a consulta por fragmento e todos os testes existentes.
- O que era técnico demais: o usuário escolhia uma "camada" pela estrutura do motor ("Escoamento potencial por trecho" e, dentro dela, quatro modos). Não havia caminho do mapa para os resultados nem do simulador para o mapa.
- PWA existente: `/pwa/` é o app de rotas do cidadão (manifesto, service worker, ícones, testado). A aplicação de análise (painel, mapa, resultados) **não era instalável**. No celular, a raiz `/` leva ao `/pwa/`, salvo com `?painel=1`.

## 2. Etapa 1: mapa de análise

**Decisão:** em vez de reescrever o mapa, foi acrescentado, no topo do painel, um bloco "O que você quer ver?" com as quatro perguntas, cada uma ligada a uma grandeza que já existia.

| Dimensão | Texto oficial na tela | Camada e modo existentes |
|---|---|---|
| A Geração | "Quanto da chuva pode se transformar em água que escoa pela superfície (geração de escoamento superficial)." | escoamento, modo "geração local" |
| B Concentração | "Para onde a água que escoa tende a convergir pelo território (concentração de escoamento superficial)." | escoamento, modo "contribuição" |
| C Topografia | "Onde o relevo apresenta condições mais favoráveis à retenção de água (propensão topográfica à retenção)." | escoamento, modo "indicador topográfico" |
| D Drenagem | "Onde estão localizados os dispositivos e as redes de drenagem cadastrados (infraestrutura de drenagem)." | camada de drenagem |

- A, B e C compartilham a cor das linhas e aparecem **uma por vez** (a tela diz isso); D é independente e se sobrepõe. Não há índice composto.
- Cada dimensão ligada mostra sua nota de limite: B "contribuição potencial, não vazão, não se soma entre trechos"; C "não é profundidade, Copernicus GLO-30 de 30 m"; D "presença no cadastro não comprova conexão, capacidade nem funcionamento".
- Com A ou B ligada, aparece a **chuva de referência ativa** ("30 mm é o percentil 75 dos totais por evento, não a média; hipotética e uniforme") e a versão dos dados.
- Navegação: link "Ler os resultados por contexto territorial", botão "Voltar à visão geral da cidade" e tratamento de endereços internos (`hashchange`: antes só funcionava ao abrir a página).
- Estados: carregando, indisponível com o motivo e botão "Tentar de novo". Trecho sem dados continua dito como "sem dados", nunca zero. No navegador sem WebGL o bloco não aparece (as camadas exigem WebGL, como já era).
- O cabeçalho agora cabe em uma linha rolável no celular (antes ocupava três linhas), e as dimensões vêm antes dos controles de vista.

**Mapa e Resultados usam os mesmos números:** `tests/test_consistencia_mapa_resultados.py` confere que as chuvas e os pacotes são os mesmos e que, para cada trecho, cenário e pacote, o valor que o painel do trecho calcula (P × aeq ÷ 1000) é o que o motor gravou (mais de mil conferências). A chuva escolhida no mapa, no simulador e nos Resultados é uma só (`Resultados.P` ⇄ `Fase3.estado.p`).

## 3. Etapa 2: simulador de cenários de cálculo

Aba **Simulador** (`#poa/simulador`), sem motor próprio: lê as três execuções já resumidas em `resultados_poa.json`. Mostra:

1. a escolha de 10, 20 ou 30 mm com a posição na série (30 mm = percentil 75 dos totais por evento, não média; série de reanálise ERA5, não pluviômetro; chuva uniforme e sem distribuição no tempo, "um evento de dois dias não equivale a uma chuva de 24 horas");
2. volume potencial da cidade por pacote (intervalos, **sem somar pacotes**, que cobrem classes diferentes) e quantis por trecho;
3. trechos por faixa de contribuição (< 100, 100 a 1.000, 1.000 a 10.000 e ≥ 10.000 m³) nos três cenários;
4. comparação entre cenários com o fator sobre 30 mm e a verificação da ordem dos trechos;
5. comparação territorial por bairro (só com 200 trechos com dados ou mais), com os valores de 10, 20 e 30 mm;
6. links para o mapa com a mesma chuva e para os Resultados.

Validação (`tests/test_simulador.py`, 8 testes): contagens por faixa **iguais à saída do motor** (`trechos_nivel2_cenarios.parquet`), p99 igual, fator 6 por trecho com erro < 1e-9, ordem dos trechos idêntica nos três cenários, escala linear dos bairros, nenhuma frase que prometa previsão, rota segura ou profundidade sem negação.

Para isso, o gerador passou a gravar `trechos_com_dados` por cenário em `resultados_poa.json` (regenerado em 26/11/2026; os 13 indicadores e os 9 achados continuam verificados).

## 4. Etapa 3: PWA e experiência mobile

- **Manifesto** `manifest.webmanifest` (escopo `./`, `start_url ./?painel=1`, ícones 192/512 e maskable reaproveitados de `pwa/`). `?painel=1` evita o redirecionamento do celular ao app de rotas.
- **Service worker** `sw.js`, versão `fm-app-v1`. Política:

| Recurso | Política |
|---|---|
| Interface, bibliotecas do mapa, landing | pré-carga na instalação; rede primeiro, cópia como reserva |
| `data/*` (resultados, territórios) | rede primeiro; offline usa a cópia salva, **marcada** (`X-FM-Copia-Salva`), e a tela avisa com a data |
| Mapa-base | só faixas já vistas (módulo `sw-mapa.js`, agora **compartilhado** com `/pwa/`, sem duplicar) |
| `/api/`, `previsao_72h.json`, `bloqueios.json` | nunca guardados |
| Tiles e fragmentos de `fase3/` e `drenagem/` (~140 MB) | nunca guardados |

- **Versão e atualização:** o rodapé mostra `Interface fm-app-vN`; ao publicar uma versão nova, o cache antigo (só `fm-app-`) é removido, com varredura dupla porque um service worker antigo pode recriar o cache durante a troca; a tela mostra "nova versão". Os caches do app de rotas e do mapa-base não são tocados.
- **Instalação:** botão "Instalar aplicativo" só aparece quando o navegador oferece (`beforeinstallprompt`); sem isso nada é prometido (por exemplo, no iOS é pelo menu do navegador).
- **Offline, o que a tela afirma:** continuam a interface, os resultados e o simulador (última cópia salva) e as áreas do mapa-base já vistas. **Dependem de conexão:** camadas de escoamento e drenagem, previsão, bloqueios, ocorrências e rotas. O aviso aparece com `navigator.onLine === false`.
- **Mockup de smartphone:** `inicio/celular.html` mostra a **aplicação real** em 390 px dentro de uma moldura de CSS (iframe; sem imagem ilustrativa) com cinco telas: visão territorial, camadas (dimensão A a 30 mm), consulta de um trecho (exemplo: Rua Álvaro Chaves, escolhido pela contribuição e pela cobertura do Método 1, **não** como ponto de alagamento), resultados e simulador. Para isso o endereço do mapa aceita `lon`, `lat`, `zoom` e `trecho` (validados: coordenadas dentro de Porto Alegre, índice inteiro).
- **CSP:** só a página do painel passou a poder ser exibida por uma página da **mesma origem** (`frame-ancestors 'self'`); todo o resto, inclusive o service worker e a landing, continua com `'none'`. O teste que fixava `'none'` na raiz foi atualizado para refletir isso e passou a conferir os demais caminhos.

Testes: `tests/test_pwa_app.py` (9, estáticos: manifesto, pré-carga existente e leve, política de não guardar, isolamento entre caches) e e2e `pwa_app.js` (instalação, cache seletivo, offline real com `setOffline`, atualização) e `celular.js`.

## 5. Preparação para publicação

Ver [`publicacao_pages_releases.md`](publicacao_pages_releases.md). Em código: `config-dados.js` (URLs-base configuráveis, relativas ou absolutas; hash esperado do `meta.json`; versão do conjunto), `tools/gerar_manifesto_publicacao.py` (versão `d-<hash>` derivada do conteúdo e verificação), `tools/auditar_integridade.py`. Teste e2e `dados_config.js`: base alternativa, hash errado recusado, hash certo carrega, indisponibilidade com "Tentar de novo".

## 6. Auditoria geral

### Funcional
Landing, Resultados, Mapa (3D e fallback 2D), Simulador, PWA e navegação entre telas foram exercidos por e2e. Links internos entre mapa, resultados e simulador funcionam (`hashchange`). Estados de erro e de ausência de dados testados.

### Científica
Mantidas e testadas: geração ≠ retenção; contribuição ≠ vazão; indicador topográfico ≠ profundidade; pacotes cobrem classes diferentes e não se somam; contribuição não se soma entre trechos; 30 mm é percentil 75 por evento, não média; a série é reanálise; DEM de 30 m não resolve depressões urbanas; drenagem é só contexto; o simulador não é hidráulico.

### Dados
`tools/auditar_integridade.py`: 19 verificações, 0 falhas (hashes dos 4 Parquets e dos da drenagem iguais aos registrados; 173 fragmentos contíguos somando 176.836 trechos; 1.884 tiles em zoom 13 a 15; 13 indicadores com os 11 campos). Gerador de resultados reproduzível (reexecutado, mesmos achados verificados).

### Segurança e qualidade

| # | Gravidade | Achado | Estado |
|---|---|---|---|
| 1 | Média | Leaflet carregado da CDN sem verificação de integridade (o MapLibre já tinha) | **Corrigido**: SRI com hashes medidos em 26/11/2026 |
| 2 | Média | Service worker antigo podia recriar o cache da versão removida | **Corrigido** (varredura dupla; escrita só em cache existente) |
| 3 | Média | Endereço interno não trocava de aba após a página aberta | **Corrigido** (`hashchange`) |
| 4 | Média | Cache da versão do app de rotas apagava o cache de outros service workers do mesmo domínio | **Corrigido** (prefixos próprios) |
| 5 | Baixa | Parâmetros da URL: lista fechada para pacote, modo e chuva; `lon`, `lat`, `zoom` e `trecho` validados por faixa | Verificado; sem XSS (valores só entram como números ou lista fixa; textos de dados passam por `esc`) |
| 6 | Baixa | `frame-ancestors 'self'` na página do painel | Decisão consciente, restrita à mesma origem; documentada |
| 7 | Baixa | Contraste e leitor de tela **não foram medidos**; foram conferidas navegação por teclado e foco nos novos botões e as cores novas por cálculo | Em aberto |
| 8 | Baixa | Desempenho com GPU e celular reais **não medido** (testes usam WebGL por software) | Em aberto |
| 9 | Informativa | Sem críticos nem altos encontrados | — |

Dependências: nenhuma nova (nem JS nem Python). Recursos externos do navegador: cdnjs (Leaflet, MapLibre, com SRI) e AWS Terrain Tiles (relevo), como antes.

## 7. Limitações e decisões em aberto

- A escolha entre Pages com Releases e R2 **não foi feita** (decisão da autora); o CORS de Releases não está verificado.
- Sem servidor, as abas que dependem da API não funcionam.
- O tamanho total (362 MB) e o prazo de 10 minutos do Pages precisam ser medidos numa publicação real.
- Conferência de contraste e leitor de tela, e desempenho em aparelho físico, ficam como pendências de QA.
- O trecho de demonstração do mockup foi escolhido do percentil 97 de contribuição; é só um exemplo de consulta.

## 8. Rodada de consolidação (26/11/2026)

Auditoria final sem novas funcionalidades e sem redesign. Nada foi commitado, enviado ou publicado.

**Cenários 10, 20 e 30 mm (substituem 10, 30 e 60 mm).** O motor foi reexecutado com `config/fase3_motor.yaml` (`precipitacoes_mm: [10, 20, 30]`) sobre os mesmos dados. Conferido: `celulas_30m`, `trechos_nivel1_*` e `trechos_contribuicao_base` saíram **byte a byte idênticos** (mesmo SHA-256); as linhas de 10 e 30 mm de `trechos_nivel2_cenarios` são idênticas às anteriores; 20 mm é exatamente 2 × 10 mm. Os 2.058 tiles e fragmentos da camada web não mudaram; só o `meta.json` (chuvas e hash do Parquet de cenários). Regenerados: `resultados_poa.json`, a landing (`inicio/index.html` e `dados.json`, com `--sem-figuras`), `docs/fase3_resultados.md` e o manifesto (versão do conjunto `d-b7f6f03555d9`, antes `d-6c3c2b28e0ee`). A verificação S1 passou a conferir 30 mm = 3 × 10 mm por trecho (erro menor que 1e-9) e a mesma ordem dos trechos. O 60 mm (percentil 92) deixa de aparecer na interface; os relatórios de experimentos antigos (`sensibilidade_hidrologica.md`, roteiros) continuam descrevendo o que foi de fato executado.

**Textos.** As quatro dimensões usam as frases oficiais, com a explicação metodológica em "Como ler" (detalhe recolhido). Nomes: Geração, Concentração, Topografia, Drenagem. A aba Resultados tinha outra taxonomia com as mesmas letras (A urbanização, B vegetação, C concentração, D drenagem); agora cada seção diz a dimensão do mapa a que pertence. A landing abre com "Como a chuva transforma o território?", a narrativa "Da chuva à estimativa de áreas com maior propensão ao acúmulo de água" e o aviso do que o estudo não prevê.

**Dados sintéticos.** A origem de cada camada: geometrias viárias e cadastro de drenagem (cadastrais); série 2017 a 2026 (reanálise ERA5 via Open-Meteo, não pluviômetro); geração, contribuição e indicador topográfico (estimativas do estudo, geradas dos Parquets, sem nenhuma entrada do servidor de demonstração); chuva e ocorrências de Porto Alegre do servidor em modo demonstração (sintéticas, só com `FM_DEMONSTRACAO` ligada e identificadas). O aviso passou a separar essas categorias. Os recursos sintéticos continuam disponíveis apenas nesse modo opcional, isolados, e não alimentam Resultados, Simulador nem o mapa de análise (teste editorial confere que `resultados.py` não os usa); por isso não foram removidos.

**Modo claro permanente.** Removidos todos os blocos `prefers-color-scheme` (10 em `style.css`, 2 em `pwa.css`), o estilo escuro do mapa-base (`escuro()` sempre falso; `estilo-escuro.json` saiu da pré-carga do service worker, mas o arquivo continua no disco), e acrescentados `color-scheme: light` e `<meta name="color-scheme" content="light">`. Não há seletor de tema. Testado no navegador com o sistema em modo escuro: fundo e texto iguais ao modo claro em cinco páginas.

**Contraste (calculado, não medido na tela).** Tokens do painel contra o fundo: texto 14,4:1; texto secundário 5,4:1; destaque 6,6:1; alerta 6,2:1; branco sobre o destaque 7,1:1. Todos acima de 4,5:1. A paleta da landing não foi calculada.

**Desempenho (medição real, mas com WebGL por software, no próprio Mac, localhost, sem limitação de rede; não representa celular ou GPU reais).** Carga da página do painel: 22 requisições e 622 KB, load em cerca de 0,2 s. Mapa pronto em 3,1 s (1280 px) e 1,4 s (390 px). Ligar a dimensão B até o estilo carregar: 11,7 s e 6,4 s (inclui 1,5 s de espera fixa e renderização por software). Total depois dessa interação: 242 requisições e 23,8 MB (1280 px; 6,5 MB de fase3, 1,5 MB de mapa-base, 4,6 MB de API); 163 requisições e 18 MB em 390 px. Memória de JavaScript: 165 MB e 114 MB. Estimativas para aparelhos reais: não feitas.

**Achados da rodada**

| # | Gravidade | Achado | Estado |
|---|---|---|---|
| 1 | Média | Modo escuro por `prefers-color-scheme` ativo em `style.css`, `pwa.css` e no mapa-base, contra a regra de modo claro permanente | Corrigido; teste editorial e e2e |
| 2 | Média | Cenário de 60 mm em mapa, Resultados, Simulador, landing, motor, testes e docs; escolha diferente da direção de produto | Corrigido com reexecução do motor; dados de base idênticos |
| 3 | Média | O aviso de demonstração dizia "em Porto Alegre, a chuva e as ocorrências são sintéticas" sem distinguir as estimativas do estudo | Corrigido |
| 4 | Média | Letras A a D com dois significados (mapa e Resultados) | Corrigido (rótulos das seções) |
| 5 | Baixa | Teste e2e da drenagem clicava num ponto de rede onde havia um poço desenhado por cima; passava por acaso do layout | Teste corrigido para evitar pontos sob o clique; não era falha do produto |
| 6 | Baixa | `inicio/celular.html` e `inicio/aplicativo.html` sem declaração de esquema de cor | Corrigido |
| 7 | Média | Os assets de Releases não enviam CORS (medido em um release público de terceiros) | Documentado; recomendação evita leitura direta |
| 8 | Baixa | Leitor de tela e contraste na tela não medidos; desempenho em aparelho real não medido | Em aberto |

