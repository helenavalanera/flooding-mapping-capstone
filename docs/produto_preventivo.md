# Mobilidade preventiva: dashboard operacional e PWA

Duas interfaces sobre **o mesmo serviço** (`servico.py`, exposto por `servidor.py`): o dashboard desktop e a PWA
mobile. Elas não conversam entre si; ambas consultam a API, então uma interdição confirmada no painel é a próxima
coisa que uma análise de rota na PWA enxerga.

```
make rede     # uma vez: data/processed/rede_poa.parquet (ruas + terreno + nomes), a partir de data/interim
make servir   # http://127.0.0.1:8000/  (dashboard)   /pwa/  (mobilidade preventiva)
```

## Três domínios separados

| Pergunta | Módulo | Natureza |
|---|---|---|
| Onde a água tende a se acumular? | `risco_trecho.indice_fisico` | índice físico **relativo** (percentil). Não é probabilidade nem modelo treinado |
| Quando um trecho pode acumular água? | `risco_trecho` + `chuva_horaria` | **baseline determinístico**, sem validação em vias |
| Quais deslocamentos são afetados? | `rotas` | roteamento e simulação em grafo |

O modelo municipal por dia (registros do S2iD) **não é usado** aqui e não prevê alagamento em vias. Nenhum rótulo
municipal é propagado a trechos, e trecho sem ocorrência não é tratado como negativo.

## Risco por trecho (metodologia)

`escore = fator de chuva (0–1) × peso do trecho (0–1)`

* **Fator de chuva**: total em 24 h e hora mais intensa, com janelas que terminam na hora considerada (nunca olha
  adiante), mapeados linearmente de modo que os níveis observados em dias com bloqueios em Porto Alegre
  (`reports/qa/rain_calibration.json`: limites inferiores 26,2 mm/24 h e 3,5 mm/h = nível médio; 55,9 mm e 9,0 mm = alto)
  deem 0,4 e 1. Condição antecedente (72 h antes da janela) multiplica por 1,15. O fator **recua a zero em 6 h secas**: a água
  sai da via em horas, as janelas de 24 h não.
* **Peso**: rampa sobre o percentil do índice físico (0 até o percentil 85, 1 no topo). Ocorrência próxima e ativa eleva
  o peso a um piso (confirmada 0,9; reportada 0,6; × confiabilidade).
* **Classes**: Atenção ≥ 0,25; Alto ≥ 0,60. Com chuva no nível médio ~5% da malha com índice fica em Atenção; com chuva
  forte ~5,5% em Alto e ~5% em Atenção. Sem a rampa, a classe Alto chegava a 61% da malha.
* **Sem dado de terreno → sem estimativa** (não é risco baixo). 39% dos segmentos (69 mil de 177 mil) não têm índice.
* A chuva é **uma série para a cidade** (grade de ~10 km): diz quando chove, não onde.

Todos os parâmetros estão em `config/analysis.yaml` (bloco `risco_trecho`); os que não têm base nos dados estão marcados
`PROVISÓRIO` e **não foram ajustados a ocorrências**.

### O que foi e o que não foi verificado

* Ancoragem da chuva: usa os mesmos eventos documentados (circular para o fator de chuva; não é validação).
* `python -m flooding_mapping.rede_poa --verificar` → `reports/ml/risco_trecho_descritivo.json`: os segmentos junto a 19
  bloqueios documentados (4 datas) têm percentil mediano 75 (geral 50) e 59% ficam no terço superior (acaso ~30%).
  **A regra só de cota baixa faz igual ou melhor** (77 e 63%): os demais fatores não mostram ganho. Descritivo; unidades
  não independentes.
* **Não há previsão viária validada.** Faltam ocorrências georreferenciadas suficientes; o que existe é um baseline
  transparente cujos resultados são sempre apresentados como estimativa.

## Roteamento

Dijkstra sobre o grafo OSM (`carro` e `pe`). Custo do trecho = tempo + `600 s/km × escore × confiabilidade × aversão`,
com o escore avaliado no **horário estimado de passagem** (saída + tempo acumulado). **Interdição confirmada remove o
trecho; risco previsto só penaliza.** Saem: rota habitual (menor tempo), a de menor exposição estimada (se existir
alguma) e uma alternativa distinta (compartilha ≤ 70% com as demais, tempo ≤ 1,5× + 10 min). Nenhuma rota é chamada de
segura.

Limites: velocidades de fluxo livre, sem trânsito, semáforos ou restrições de conversão; sem ônibus (sem JDK para o r5py e
GTFS vencido); cada rota é o melhor caminho sob penalidade dependente do tempo, não o ótimo exato de um grafo
dependente do tempo; vias sem terreno somam zero de penalidade e o trecho é reportado como "sem estimativa". Um
processo atende poucos usuários simultâneos (consulta de ~1–5 s).

Não foi integrado OSRM/Valhalla: exigiriam serviço separado e não aceitam penalidade de risco por horário de passagem.

## Ocorrências

`ocorrencias.py`: fonte, tipo, localização, data/hora, início/fim, severidade, impacto, situação (reportada,
confirmada, descartada), confiabilidade, origem do registro e histórico de transições.

* Relato de usuário nasce **sempre** `reportada`/`baixa`; o chamador não escolhe outra coisa.
* Só `POST /api/ocorrencias/{id}` com `OPERADOR_TOKEN` e evidência escrita (≥ 10 caracteres) muda a situação. Sem o
  token configurado, a rota fica desativada.
* Só `confirmada` + impacto `interdicao` fecha um trecho. Relato apenas eleva o risco estimado.
* Retenção: registros com mais de 90 dias são apagados ao iniciar o servidor. Não há identificador de usuário.

## Camada de linguagem (Gemini)

`linguagem/`: explica e contextualiza; **nunca calcula**. Configuração em `.env` (copie `.env.example`):
`GEMINI_API_KEY` e `GEMINI_MODEL` (sem valor padrão: sem os dois, tudo funciona com textos determinísticos).

* API REST oficial via `requests`; a chave vai em cabeçalho, nunca em URL, log ou resposta.
* Cinco operações com contrato fechado (`get_weather_forecast`, `analyze_route_risk`, `calculate_alternative_routes`,
  `get_nearby_incidents`, `get_risk_explanation`): argumento desconhecido, tipo errado ou valor fora do intervalo é
  recusado; a análise é vinculada pelo backend (o provedor não escolhe qual).
* Recebe só agregados: tempos, km por classe, nomes das vias mais expostas, horários de passagem. Nunca origem, destino,
  coordenadas, trajeto completo, endereço ou texto livre de usuários.
* Chamado só se o usuário pedir e a rota habitual tiver trecho em Atenção/Alto. Limite local de 20/min e cache de 15 min.
* Qualquer falha (não configurado, chave recusada, limite, tempo esgotado, 5xx, resposta inválida) devolve o texto
  determinístico com o motivo. Resposta que afirme que uma rota é segura é descartada.
* Relatos podem ser estruturados pelo provedor (esquema com valores fechados); a localização vem do app, nunca do texto.

**Estado da validação:** testado com cliente simulado (falhas, ciclo de operações, privacidade dos resumos). **A chamada
real à API não foi executada** porque não há chave configurada.

## Privacidade (LGPD)

* Lugares e trajetos habituais ficam só no aparelho (`localStorage`); "Apagar tudo" remove tudo.
* Localização: consentimento explícito, uma posição por ação, só em primeiro plano; sem `watchPosition`. Revogável.
* O servidor recebe as coordenadas de uma análise só para calcular; ela vive em memória (30 min), é apagada ao iniciar
  outra ou fechar o app. Não há log de acesso nem de corpos de requisição.
* O service worker nunca guarda respostas da API.
* Relatos: texto e ponto, sem identificação; separados de qualquer dado pessoal.

## Interfaces

* **Dashboard**: Visão geral, Mapa (estado e Porto Alegre), Previsão, Mobilidade, Ocorrências, Proveniência.
  Observado, previsto, simulado e confirmado têm selo, cor e traço distintos. Sem o servidor, a versão estática mostra só
  o mapa estadual, com aviso.
* **PWA** (`/pwa/`): lugares e trajetos habituais, origem/destino, modal, horário, clima previsto, alerta com motivos,
  três rotas com tempo × exposição, relato e privacidade. A escolha da rota é do usuário.

Verificado em navegador (Chromium) com um temporal **sintético** e a malha real: fluxos completos, sem erro de console,
sem transbordo horizontal em 360/390/768 px e em 390 px no dashboard, e modo offline. Esses testes de navegador não estão
no repositório (exigem Playwright); os testes automatizados cobrem a lógica, os contratos e o servidor.

## O que falta (depende de você)

* Chave do Gemini em `.env` para validar a integração real.
* Hospedagem do servidor (o GitHub Pages não executa Python). Para uma interface hospedada fora do servidor, defina
  `CORS_ORIGEM` e o endereço da API na `<meta name="api-base">`.
* `OPERADOR_TOKEN` e um procedimento de confirmação de ocorrências; sem ocorrências confirmadas o roteamento não bloqueia nada.
* Mais ocorrências georreferenciadas para, só então, treinar e validar um modelo viário.
