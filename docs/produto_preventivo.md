# Flooding Mapping: inteligência territorial e mobilidade preventiva

Uma plataforma, duas escalas de demonstração, duas interfaces sobre **o mesmo serviço** (`servico.py`, exposto por
`servidor.py`). O dashboard e a PWA não conversam entre si: ambos consultam a API, então uma interdição confirmada no painel
é a próxima coisa que uma análise de rota na PWA enxerga.

| Demonstração | Objetivo | O que existe |
|---|---|---|
| **Rio Grande do Sul** | inteligência territorial e monitoramento regional | limites municipais, malha DAER, estimativa municipal de 72 h, bloqueios e registros S2iD, cobertura calculada por município e rodovia |
| **Porto Alegre** | operação urbana e mobilidade preventiva | rede de ruas, relevo, chuva horária, baseline de risco por trecho, ocorrências, rotas para carro e a pé |

## Como executar

```
make rede     # uma vez: data/processed/rede_poa.parquet (ruas + terreno + nomes), a partir de data/interim
make servir   # http://127.0.0.1:8000/  dashboard   |   /pwa/  mobilidade preventiva
```

O dashboard também funciona **estático** (GitHub Pages, `make estado-site`): sem o servidor, o mapa estadual, a visão geral, a
previsão municipal, as ocorrências estaduais e a proveniência continuam; tudo o que depende do servidor fica **inativo com aviso**.
O servidor local serve também os arquivos gerados em `site/` (previsão estadual), sempre depois do código-fonte.

### Variáveis de ambiente (`.env`, ignorado pelo Git; modelo em `.env.example`)

| Variável | Para quê | Sem ela |
|---|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | contextualização por provedor de linguagem | tudo funciona com textos determinísticos |
| `OPERADOR_TOKEN` | confirmar ou descartar ocorrências | essas rotas ficam desativadas (403) |
| `CORS_ORIGEM` | origem permitida para um front-end hospedado fora do servidor | só a mesma origem |

Operador: `Authorization: Bearer <OPERADOR_TOKEN>`. Credencial inválida é contada por cliente e bloqueia por um minuto após 8
tentativas (429); o bloqueio vale também para a credencial correta (atrás de um proxy, todos os clientes compartilham o mesmo
endereço: ver pendências).

## Arquitetura

```
config/territorios.yaml ──► capacidades (o que cada região oferece)           ┐
dados DAER/S2iD/IBGE ─────► cobertura.py ──► cobertura (onde há dados)        ├─► data/territorios.json, cobertura_rs.json
dados e rede carregados ──► qualidade (completude, atualidade, confiabilidade)┘        │
                                                                                        ▼
Open-Meteo ► chuva_horaria ► risco_trecho ► rotas ► servico ► servidor (API) ◄── dashboard (painel.js, mapa.js)
                                  ▲            ▲        ▲                    ◄── PWA (pwa/pwa.js)
                   ocorrencias ───┴────────────┘        └─ linguagem/ (Gemini, só agregados)
```

Três domínios analíticos, separados:

| Pergunta | Módulo | Natureza |
|---|---|---|
| Onde a água tende a se acumular? | `risco_trecho.indice_fisico` | índice físico **relativo** (percentil). Não é probabilidade nem modelo treinado |
| Quando um trecho pode acumular água? | `risco_trecho` + `chuva_horaria` | **baseline determinístico**, sem validação em vias |
| Quais deslocamentos são afetados? | `rotas` | roteamento e simulação em grafo |

O modelo municipal por dia (registros do S2iD) **não é usado** nas vias e não prevê alagamento em vias. Nenhum rótulo municipal
é propagado a trechos, e trecho sem ocorrência não é tratado como negativo.

## Cobertura, capacidades e qualidade

Três conceitos, três lugares, sem condicionais por região na interface:

* **Capacidades** (`config/territorios.yaml`): o que cada região oferece (`disponivel`, `parcial`, `indisponivel`, com motivo e se
  exige o servidor). A interface lê o arquivo publicado (`data/territorios.json`) e mostra uma capacidade indisponível **com o
  motivo**, nunca como zero. A validação recusa risco por trecho como "disponível" (`tests/test_cobertura.py`), e um teste garante
  que toda camada prometida é desenhada pelo mapa.
* **Cobertura** (`cobertura.py`, `python -m flooding_mapping.cobertura`): onde há dados, em números calculados dos dados reais.
* **Qualidade**: completude (frações do km), atualidade (horário de cada fonte, lido dos próprios arquivos) e confiabilidade (texto
  de cada fonte). Nenhum percentual é digitado.

**Método da cobertura estadual.** Cada segmento da malha DAER (~1 km, sem os trechos planejados) é atribuído ao município que contém
o seu ponto médio. Por município e por rodovia calculam-se, por **comprimento (km)**: fração com índice físico, fração com tráfego
(VDM) e pontes na simulação. A **classe** depende de quatro dimensões: malha DAER, índice físico, tráfego e registros hidrológicos do
S2iD (só para municípios), cada uma com mínimo configurado (80% do km para índice e tráfego). "Dados disponíveis" exige todas; "dados
insuficientes" é a região sem malha nem registro S2iD (só há meteorologia); as demais são "cobertura parcial". A classe descreve
**existência de dados, não validade de análise**.

Resultado (497 municípios, 483 rodovias): **128 municípios com dados disponíveis, 369 com cobertura parcial, 0 insuficientes**. O índice
físico cobre 100% do km da malha; o tráfego, 36%. Um primeiro critério, só com o índice físico, classificava 487 de 497 como
"disponíveis" e escondia a falta de tráfego, por isso foi abandonado.

**Porto Alegre.** Índice físico em 72% do km dirigível (5.483 km), 59% do caminhável (6.452 km) e **0% dos 1.159 km só de pedestres**.
Trechos sem índice ficam **sem estimativa**, que não é risco baixo; a comparação de rotas avisa quando a menor exposição vem de uma
parcela relevante do trajeto sem dado.

## Meteorologia

`chuva_horaria.py`. **Uma série horária para a cidade inteira** (Open-Meteo, grade de cerca de 10 km): diz quando chove, não onde. O
passado recente é **análise do modelo, não leitura de pluviômetro**; as horas à frente são previsão. Unidade (mm) e fuso são verificados
na resposta. Os dados valem 6 h: a consulta é renovada a cada 30 min, e se a renovação falhar o último valor segue sendo usado, marcado
como defasado, **até as 6 h**. Depois disso o serviço responde que a chuva está indisponível (HTTP 503 com a última atualização
conhecida), as rotas saem só com tempo e distância, sem estimativa de risco, e o alerta é `sem_dados`. A tela diz isso e que não
significa rota sem risco. Todo texto de risco repete que a chuva é regional. O recuo de 6 h do fator de chuva continua **provisório**: os
eventos documentados não trazem evidência a favor nem contra.

## Risco por trecho (metodologia)

`escore = fator de chuva (0–1) × peso do trecho (0–1)`

* **Fator de chuva**: total em 24 h e hora mais intensa, janelas que terminam na hora considerada (nunca olha adiante), ancorados nos
  níveis observados em dias com bloqueios em Porto Alegre (`reports/qa/rain_calibration.json`: limites inferiores 26,2 mm/24 h e
  3,5 mm/h = 0,4; 55,9 mm e 9,0 mm = 1). Condição antecedente (72 h antes) multiplica por 1,15. O fator **recua a zero em 6 h secas**.
* **Peso**: rampa sobre o percentil do índice físico (0 até o percentil 85, 1 no topo). Ocorrência próxima e ativa eleva o peso a um piso.
* **Classes**: Atenção ≥ 0,25; Alto ≥ 0,60. Chuva no nível médio: ~5% da malha com índice em Atenção; chuva forte: ~5,5% em Alto e ~5% em Atenção.
* A chuva é **uma série para a cidade** (grade de ~10 km): diz quando chove, não onde.

Parâmetros em `config/analysis.yaml` (bloco `risco_trecho`); os sem base nos dados estão marcados `PROVISÓRIO` e **não foram ajustados a ocorrências**.

### Auditoria dos parâmetros (`python -m flooding_mapping.auditoria_risco` → `reports/ml/risco_trecho_auditoria.json`)

* **Cobertura do índice** por modal, acima. Só pedestres: 0%.
* **Recuo de 6 h**: nos 4 eventos documentados a chuva continuou até a noite, então eles **não restringem** a duração do recuo (sem evidência a favor nem contra; segue provisório).
* **Em 2022-03-06** o fator na hora do reporte fica abaixo do corte de Atenção para qualquer trecho: o baseline não sinalizaria esse evento.
* Os eventos ancoram os níveis de chuva (limites inferiores): reconferi-los contra eles é circular e não os valida.
* `python -m flooding_mapping.rede_poa --verificar` (`reports/ml/risco_trecho_descritivo.json`): segmentos junto a 19 bloqueios (4 datas) têm percentil mediano 75 (geral 50), mas a regra só de cota baixa faz igual ou melhor (77): os demais fatores não mostram ganho.
* **Confronto com os eventos documentados** (19 bloqueios geocodificados, 4 datas; `reports/ml/risco_trecho_auditoria.json`): o baseline sinalizou
  **4 dos 19** em algum horário do dia e **2 na hora do reporte**. Dos 15 não detectados, 9 têm peso zero (segmentos abaixo do percentil de
  corte), 6 tiveram chuva abaixo do nível que sinaliza esses trechos, e em 2 o sinal veio em outra hora do dia. Nenhum corte do índice detecta
  os eventos sem sinalizar uma parcela grande da malha (curva do corte no relatório), então **não há ajuste de parâmetro que resolva isso**, e
  nenhum foi feito. Os eventos são poucos e concentrados em quatro datas.
* **Dias sinalizados sem registro:** em 2.863 dias (2019-01-01 a 2026-11-02), alguma via ficou em Atenção em 682 e em Alto em 305; só 4 dias
  têm bloqueio documentado. **Ausência de registro não é exemplo negativo**: não são falsos alertas comprovados, apenas dias que não se consegue conferir.
* **Testes de sensibilidade** (`tests/test_sensibilidade_risco.py`): a ordem dos trechos e as classes mudam de forma previsível com chuva, corte e peso.
* **Três conceitos separados:** *suscetibilidade espacial* (índice físico do terreno, relativo, não é probabilidade), *previsão temporal* (apenas a chuva futura e a regra explícita do fator) e *impacto na mobilidade* (rotas e simulação de fechamento). O produto os mantém distintos e não promove o conjunto a previsão de alagamento.
* **Não há previsão viária validada.** Faltam ocorrências georreferenciadas suficientes. A Proveniência da interface mostra o que se pode e o que
  não se pode afirmar (nunca "rota segura" nem "alagamento previsto nesta rua").

## Roteamento

Dijkstra sobre o grafo OSM inteiro (`carro` e `pe`), restrito ao maior componente fortemente conexo de cada modal (carro: 96,7% do km
permitido alcançável; a pé: 90,7%). Custo = tempo + `600 s/km × escore × confiabilidade × aversão`, com o escore no **horário estimado de
passagem**. **Interdição confirmada é bloqueio rígido nos dois modais; risco previsto só penaliza.** Saem: a rota habitual (menor tempo), a
de menor exposição estimada (se houver) e uma alternativa distinta (compartilha ≤ 70%, tempo ≤ 1,5× + 10 min). Nenhuma rota é chamada de segura.

Convenções do OSM aplicadas na construção da rede (`rede_poa.construir`): sentido único (incluindo rotatórias sem a marca), acesso privado
ou fechado, estacionamento e garagem fora do carro, escadas contadas à parte (km de escadas na análise).

**Auditoria** (`python -m flooding_mapping.auditoria_rotas` → `reports/ml/rotas_auditoria.json`): conferência contra um caminho mínimo de
referência (networkx) em 100 pares por modal, **0 diferenças** em carro e a pé; é auditoria do cálculo, não valida a qualidade de nenhum
deslocamento real. A busca já teve um corredor em torno da reta origem-destino e ele foi **removido** quando produziu uma rota a pé 12 min
pior que a de referência.

Limites: velocidades de fluxo livre por classe de via (a velocidade máxima legal não é usada), sem trânsito, semáforos, restrições de conversão,
existência de calçada nem inclinação no tempo a pé; sem ônibus (sem JDK para o r5py e GTFS vencido); sem navegação curva a curva; cada rota é o
melhor caminho sob penalidade dependente do tempo, não o ótimo exato; vias sem terreno somam zero de penalidade e são reportadas. Um processo
atende poucos usuários simultâneos (consulta de ~1–5 s). Não foram integrados OSRM/Valhalla: exigiriam serviço separado e não aceitam
penalidade de risco por horário de passagem.

## Ocorrências

`ocorrencias.py`: fonte, tipo, localização, data/hora, início/fim, severidade, impacto, situação (reportada, confirmada, descartada),
confiabilidade, origem do registro e histórico de transições.

* Relato de usuário nasce **sempre** `reportada`/`baixa`. Só o operador (token + evidência escrita ≥ 10 caracteres) muda a situação, e **declara o impacto ao confirmar** (`interdicao`, `parcial`, `nenhum` ou `desconhecido`); só `confirmada` com impacto `interdicao` fecha um trecho. O fluxo completo (relato, confirmação, trecho bloqueado na rota) é testado pela API HTTP.
* A **listagem pública omite o texto livre**: um relato não verificado pode conter dado pessoal digitado por terceiros. Só o operador autenticado o recebe.
* **Persistência**: arquivo JSON Lines (`data/operacional/`, fora do Git), `fsync` a cada gravação, linhas truncadas ignoradas e contadas na leitura, retenção de 90 dias por reescrita atômica. É suficiente para um processo; **não** para vários processos escrevendo (ver pendências).
* Registros do S2iD e bloqueios da CPRv BM (RS) são registros oficiais de terceiros e **não** passam pela classificação reportada/confirmada/descartada.

## API

| Rota | Método | Quem | Notas |
|---|---|---|---|
| `/api/saude`, `/api/territorios` | GET | todos | territórios: capacidades + cobertura |
| `/api/visao-geral`, `/api/previsao`, `/api/risco?h=`, `/api/trecho?id=`, `/api/proveniencia` | GET | todos | Porto Alegre; 240 leituras/min por cliente |
| `/api/ocorrencias` | GET | todos (sem texto livre); operador (completo) | |
| `/api/rotas`, `/api/explicacao`, `/api/assistente` | POST | todos | 20, 10 e 10 por minuto |
| `/api/relatos` | POST | todos | 10/min; entra como `reportada` |
| `/api/ocorrencias/{id}` | POST | operador | confirmar ou descartar |
| `/api/analises/{id}` | DELETE | quem tem o id | apaga a análise da memória |

`/api/saude` traz métricas em memória (contagens, latências, falhas) e, só para o operador, o diagnóstico de origem do cliente atrás de proxy. Corpo máximo de 8 KB; erros em `{"erro": "..."}` (422 validação, 403 autorização, 404, 429, 500 sem detalhes); sem log de acesso nem de corpos; CORS só para `CORS_ORIGEM`; política de segurança de conteúdo restrita (workers e tiles só do necessário).

## Camada de linguagem (Gemini)

`linguagem/`: explica e contextualiza; **nunca calcula**. API REST oficial via `requests` (chave em cabeçalho, nunca em URL ou log). Cinco
operações com contrato fechado; recebe só agregados (tempos, km por classe, nomes das vias mais expostas, horários), nunca origem, destino,
coordenadas ou texto livre de usuários. Chamada só se o usuário pedir e houver risco a explicar; limite local de 20/min e cache de 15 min.
Qualquer falha devolve o texto determinístico com o motivo; resposta que afirme que uma rota é segura é descartada.

**Assistente contextual** (`linguagem/assistente.py`, `POST /api/assistente`): para um trecho, uma rota, um município ou uma rodovia, o contexto vira
um resumo estruturado sem coordenadas, com a lista do que **falta**. As perguntas sugeridas ("Por que este trecho está em atenção?", "O que
explica esta classificação?", "O que muda entre estas rotas?", "Quais informações estão indisponíveis?") têm resposta determinística; o
provedor só reformula, e a pergunta livre do usuário é tratada como dado não confiável.

**Estado:** chamadas reais ao provedor foram executadas e estão registradas, com o que não foi validado, em
[`validacao_gemini.md`](validacao_gemini.md). A chave fica só no `.env`.

## Interfaces

**Dashboard.** Seletor de território no cabeçalho e seis áreas: Visão geral (as cinco perguntas: o que acontece, onde estão os pontos de
atenção, como pode evoluir, quais deslocamentos podem ser afetados, que informações sustentam), Mapa, Condições e previsão, Mobilidade,
Ocorrências e Proveniência (inclui a matriz do que cada região oferece). Observado, previsto, simulado e confirmado têm selo, cor e traço próprios.

**Mapa (um controlador, dois motores).** Com WebGL: MapLibre GL JS 4.7.1 (BSD-3, fixado com hash de integridade). **Sem WebGL: Leaflet, com as mesmas camadas e seleção nos dois territórios** (ocorrências, interdições, trechos de atenção, rotas, municípios, rodovias); só o relevo e a vista inclinada exigem WebGL, e o painel diz isso. O mapa ocupa a tela e os painéis flutuam sobre ele, translúcidos (folha inferior recolhível no celular); onde o navegador não faz desfoque, o painel fica quase opaco. Detalhes do motor com WebGL: Terreno com elevação (AWS Terrain Tiles, público, sem chave),
inclinação, rotação, camadas por território, seleção de município, rodovia e trecho com painel contextual, destaque das rotas e dos trechos
de atenção, transição entre escalas. **Justificativa:** o MapLibre integra-se ao mapa atual sem Three.js e preserva uma alternativa 2D
(botão 2D) e o motor Leaflet, usado também sem WebGL. O relevo é só visual: o exagero vertical (1×–3×) é escolhido pela pessoa
e declarado, o modelo pode ter artefatos sobre água e vegetação, e a elevação **não entra em nenhum cálculo de risco**. Nenhuma profundidade
ou extensão de lâmina d'água é desenhada.

**Assistente no painel:** ao selecionar um trecho, uma rota, um município ou uma rodovia, uma seção expansível oferece as perguntas sugeridas e a pergunta livre, e declara se a resposta é texto padrão ou reformulada por provedor externo.

**PWA** (`/pwa/`): o mapa é a tela. Um cartão escuro de orientação mostra a rota selecionada e o que há adiante (distância até o primeiro trecho de atenção
e interdições consideradas; **sem instruções de manobra**, porque o backend não as fornece); uma barra lateral mostra onde a exposição estimada se
concentra ao longo da rota; a folha inferior alterna entre o resumo (tempo, distância, chegada, indicador de exposição, situação dos dados, rotas
em cartões) e os detalhes (condições com fonte e validade, trade-offs, trechos de atenção, ocorrências no trajeto, quatro perguntas sugeridas e a
explicação contextualizada sob pedido), por botão e sem depender de arrastar. Controles flutuantes: localização, enquadrar rota, camadas e
legenda, relatar. Ocorrências e interdições aparecem com símbolo e texto, não só cor. Sem dados de chuva a tela diz que não há estimativa de risco.
Verificação dos trajetos habituais sob demanda (sem segundo plano nem notificações), 3D opcional baixado só ao pedir, aviso de nova versão,
funciona inteira sem localização. Guia completo: [`guia_de_uso.md`](guia_de_uso.md). Origem e destino não são buscados por endereço (exigiria um geocodificador de terceiros).

**Privacidade.** Lugares e trajetos só no aparelho; localização com consentimento explícito, uma posição por ação, em primeiro plano; o
servidor guarda a análise 30 min em memória e a apaga ao iniciar outra ou fechar o app; sem log de acesso; o service worker nunca guarda a API.

## Testes

```
pytest                       # lógica, contratos, serviço, servidor, cobertura, auditorias (resultados em docs/qa_relatorio_final.md)
PLAYWRIGHT_CORE=... CHROME_PATH=... pytest tests/test_e2e_navegador.py
```

Categorias, que não se misturam nos relatórios: **unitários e de contrato** (lógica, serviço, servidor, ocorrências, rotas, meteorologia),
**auditorias** (rotas contra caminho de referência, risco contra eventos documentados, sensibilidade), **integração HTTP** (fluxo do operador,
proxy, métricas, 503 sem chuva), **navegador** (abaixo) e **chamadas reais ao provedor de linguagem** (manuais, em `validacao_gemini.md`).

Os de navegador exigem Chromium e `playwright-core` (não são dependências do projeto) e rodam com a rede real de Porto Alegre e uma chuva
**sintética declarada** (`tests/e2e/servidor_demo.py`). Cobrem dashboard (RS/Porto Alegre, 3D/2D, seleção, assistente, capacidades, rotas no mapa,
estado sem chuva), **mapa 2D num navegador sem WebGL nos dois territórios**, PWA (consentimento, lugares, trajetos, ordem da análise, perguntas sugeridas,
3D sob demanda, privacidade, offline), atualização do service worker e a ausência de transbordo horizontal em 360, 390, 768, 1024 e 1400 px.
O WebGL por software é lento (cerca de 3 minutos no total). **Teste em dispositivo físico: não executado** (não havia aparelho disponível); os
testes de navegador emulam tela e toque, e não substituem GPU, sensores e rede reais.

## Limitações e pendências

* **Documentos relacionados:** [`render.md`](render.md) (hospedagem no Render: custos, checklist, o que não foi feito), [`qa_mobile_fisico.md`](qa_mobile_fisico.md) (teste em celular, não executado), [`roteiro_apresentacao.md`](roteiro_apresentacao.md); [`demonstracao.md`](demonstracao.md) (cenário, roteiro e checklists), [`operacao_ocorrencias.md`](operacao_ocorrencias.md), [`seguranca_lgpd.md`](seguranca_lgpd.md), [`sintese_academica.md`](sintese_academica.md).
* **Hospedagem:** nada foi publicado. O servidor roda em contêiner com um volume persistente (ver [`hospedagem.md`](hospedagem.md)); o GitHub Pages
  não executa Python. Para front-end hospedado fora, `CORS_ORIGEM` e `<meta name="api-base">`. Atrás de proxy, `PROXIES_CONFIAVEIS` define de quem
  se lê o `X-Forwarded-For`; sem ele o limite por cliente enxerga um só endereço.
* **Operador:** `OPERADOR_TOKEN` configurado e o fluxo de confirmação testado; falta um procedimento humano de quem confirma e com que evidência.
  Sem ocorrências confirmadas o roteamento não bloqueia nada.
* **Persistência de ocorrências em arquivo: um processo só.** Vários processos ou histórico longo pedem um banco.
* **Risco por trecho sem validação em vias:** o confronto com os 19 eventos documentados mostra poder discriminativo baixo (4 detectados em algum
  horário, 2 na hora do reporte). Parâmetros provisórios, nenhum ajustado a ocorrências. Mais ocorrências georreferenciadas são o que falta para treinar e validar um modelo viário.
* **Chuva regional e sem pluviômetro:** uma série para a cidade; o passado é análise do modelo.
* Risco por trecho e roteamento em escala estadual não existem; ônibus não existe.
* **Provedor de linguagem:** validado em chamadas reais de amostra pequena (ver `validacao_gemini.md`); sem medição de custo e volume.
* **Dispositivo físico:** não testado.
