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
* **Não há previsão viária validada.** Faltam ocorrências georreferenciadas suficientes.

## Roteamento

Dijkstra sobre o grafo OSM (`carro` e `pe`). Custo = tempo + `600 s/km × escore × confiabilidade × aversão`, com o escore no **horário
estimado de passagem**. **Interdição confirmada remove o trecho; risco previsto só penaliza.** Saem: a rota habitual (menor tempo), a de
menor exposição estimada (se houver) e uma alternativa distinta (compartilha ≤ 70%, tempo ≤ 1,5× + 10 min). Nenhuma rota é chamada de segura.

Limites: velocidades de fluxo livre, sem trânsito, semáforos ou restrições de conversão; sem ônibus (sem JDK para o r5py e GTFS vencido);
cada rota é o melhor caminho sob penalidade dependente do tempo, não o ótimo exato; vias sem terreno somam zero de penalidade e são reportadas.
Um processo atende poucos usuários simultâneos (consulta de ~1–5 s). Não foram integrados OSRM/Valhalla: exigiriam serviço separado e não
aceitam penalidade de risco por horário de passagem.

## Ocorrências

`ocorrencias.py`: fonte, tipo, localização, data/hora, início/fim, severidade, impacto, situação (reportada, confirmada, descartada),
confiabilidade, origem do registro e histórico de transições.

* Relato de usuário nasce **sempre** `reportada`/`baixa`. Só o operador (token + evidência escrita ≥ 10 caracteres) muda a situação; só `confirmada` com impacto `interdicao` fecha um trecho.
* A **listagem pública omite o texto livre**: um relato não verificado pode conter dado pessoal digitado por terceiros. Só o operador autenticado o recebe.
* **Persistência**: arquivo JSON Lines (`data/operacional/`, fora do Git), `fsync` a cada gravação, linhas truncadas ignoradas e contadas na leitura, retenção de 90 dias por reescrita atômica. É suficiente para um processo; **não** para vários processos escrevendo (ver pendências).
* Registros do S2iD e bloqueios da CPRv BM (RS) são registros oficiais de terceiros e **não** passam pela classificação reportada/confirmada/descartada.

## API

| Rota | Método | Quem | Notas |
|---|---|---|---|
| `/api/saude`, `/api/territorios` | GET | todos | territórios: capacidades + cobertura |
| `/api/visao-geral`, `/api/previsao`, `/api/risco?h=`, `/api/trecho?id=`, `/api/proveniencia` | GET | todos | Porto Alegre; 240 leituras/min por cliente |
| `/api/ocorrencias` | GET | todos (sem texto livre); operador (completo) | |
| `/api/rotas`, `/api/explicacao` | POST | todos | 20 e 10 por minuto |
| `/api/relatos` | POST | todos | 10/min; entra como `reportada` |
| `/api/ocorrencias/{id}` | POST | operador | confirmar ou descartar |
| `/api/analises/{id}` | DELETE | quem tem o id | apaga a análise da memória |

Corpo máximo de 8 KB; erros em `{"erro": "..."}` (422 validação, 403 autorização, 404, 429, 500 sem detalhes); sem log de acesso nem de corpos; CORS só para `CORS_ORIGEM`; política de segurança de conteúdo restrita (workers e tiles só do necessário).

## Camada de linguagem (Gemini)

`linguagem/`: explica e contextualiza; **nunca calcula**. API REST oficial via `requests` (chave em cabeçalho, nunca em URL ou log). Cinco
operações com contrato fechado; recebe só agregados (tempos, km por classe, nomes das vias mais expostas, horários), nunca origem, destino,
coordenadas ou texto livre de usuários. Chamada só se o usuário pedir e houver risco a explicar; limite local de 20/min e cache de 15 min.
Qualquer falha devolve o texto determinístico com o motivo; resposta que afirme que uma rota é segura é descartada.

**Estado:** testada com cliente simulado (falhas, ciclo de operações, privacidade). **A chamada real à API não foi executada: não há chave configurada** (`.env` vazio).

## Interfaces

**Dashboard.** Seletor de território no cabeçalho e seis áreas: Visão geral (as cinco perguntas: o que acontece, onde estão os pontos de
atenção, como pode evoluir, quais deslocamentos podem ser afetados, que informações sustentam), Mapa, Condições e previsão, Mobilidade,
Ocorrências e Proveniência (inclui a matriz do que cada região oferece). Observado, previsto, simulado e confirmado têm selo, cor e traço próprios.

**Mapa 3D (MapLibre GL JS 4.7.1, BSD-3, fixado com hash de integridade).** Terreno com elevação (AWS Terrain Tiles, público, sem chave),
inclinação, rotação, camadas por território, seleção de município, rodovia e trecho com painel contextual, destaque das rotas e dos trechos
de atenção, transição entre escalas. **Justificativa:** o MapLibre integra-se ao mapa atual sem Three.js e preserva uma alternativa 2D
(botão 2D) e o **mapa clássico em Leaflet**, usado também sem WebGL. O relevo é só visual: o exagero vertical (1×–3×) é escolhido pela pessoa
e declarado, o modelo pode ter artefatos sobre água e vegetação, e a elevação **não entra em nenhum cálculo de risco**. Nenhuma profundidade
ou extensão de lâmina d'água é desenhada.

**PWA** (`/pwa/`): etapas visíveis, condições antes da análise, alerta como primeira leitura, comparação das rotas, trechos de atenção por via,
verificação dos trajetos habituais sob demanda (sem segundo plano nem notificações), estados vazios e de erro com ação, 3D opcional baixado só
ao pedir, aviso de nova versão. Funciona inteira sem localização (pontos no mapa).

**Privacidade.** Lugares e trajetos só no aparelho; localização com consentimento explícito, uma posição por ação, em primeiro plano; o
servidor guarda a análise 30 min em memória e a apaga ao iniciar outra ou fechar o app; sem log de acesso; o service worker nunca guarda a API.

## Testes

```
pytest                       # lógica, contratos, serviço, servidor, cobertura (401 testes automatizados)
PLAYWRIGHT_CORE=... CHROME_PATH=... pytest tests/test_e2e_navegador.py
```

Os de navegador exigem Chromium e `playwright-core` (não são dependências do projeto) e rodam com a rede real de Porto Alegre e uma chuva
**sintética declarada** (`tests/e2e/servidor_demo.py`). Cobrem dashboard (RS/Porto Alegre, 3D/2D, seleção, capacidades, rotas no mapa), PWA
(consentimento, lugares, trajetos, 3D sob demanda, privacidade, offline), atualização do service worker e a ausência de transbordo horizontal
em 360, 390, 768 e 1400 px. O WebGL por software é lento (cerca de 3 minutos no total).

## Limitações e pendências

* Chave do Gemini e teste real da integração. Hospedagem do servidor (o GitHub Pages não executa Python); para front-end hospedado fora,
  `CORS_ORIGEM` e `<meta name="api-base">`.
* `OPERADOR_TOKEN` e um procedimento de confirmação; sem ocorrências confirmadas o roteamento não bloqueia nada.
* Atrás de proxy, o limite por cliente enxerga um só endereço (o cabeçalho `X-Forwarded-For` não é confiado).
* Persistência de ocorrências em arquivo: um processo só. Vários processos ou histórico longo pedem um banco.
* Mais ocorrências georreferenciadas para só então treinar e validar um modelo viário. Risco por trecho em escala estadual e roteamento estadual não existem.
* O mapa clássico mostra só o Rio Grande do Sul; para Porto Alegre sem WebGL, use Mobilidade (mapa 2D de rotas).
