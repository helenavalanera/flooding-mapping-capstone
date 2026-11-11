# Síntese para a apresentação acadêmica: resultados, limites e conclusão

Este texto reúne o que o projeto entregou, com as evidências que existem no repositório, e delimita o que **não** foi demonstrado.
Ele não cria critérios de avaliação: não foram fornecidos critérios institucionais, e o que segue segue a proposta (`docs/proposta.md`) e o README.

## 1. Problema e objetivo

Alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano. O estudo mede quanto da mobilidade
urbana deixa de ser alcançável quando trechos documentados e os mais propensos a alagar são interditados (pergunta e indicadores no
README), e entrega essa análise numa plataforma de **inteligência territorial e mobilidade preventiva**: um painel para análise e uma PWA
para quem vai se deslocar. O foco da plataforma é Porto Alegre; o Rio Grande do Sul entra como monitoramento regional.

**Escopo da entrega.** Rotas de carro e a pé; interdições confirmadas por operador; meteorologia; risco estimado por trecho como
baseline experimental; assistente contextual. **Fora do escopo:** transporte público no produto (o GTFS publicado venceu e o r5py exige JDK,
ambiente sem ele), navegação curva a curva, aplicativo nativo, rastreamento em segundo plano, modelo preditivo viário e operação pública.

## 2. O que foi construído

| Componente | Situação | Onde |
|---|---|---|
| Serviço de análise (API Python, um processo) | implementado e testado | `src/flooding_mapping/servico.py`, `servidor.py` |
| Roteamento carro e a pé com penalidade de risco no horário de passagem | implementado, auditado contra caminho de referência | `rotas.py`, `auditoria_rotas.py` |
| Meteorologia horária com validade de 6 h e estados de falha | implementada e testada | `chuva_horaria.py` |
| Risco por trecho (baseline determinístico) | implementado; **sem validação em vias** | `risco_trecho.py`, `auditoria_risco.py` |
| Ocorrências, confirmação por operador e interdição efetiva nas rotas | implementado; fluxo HTTP testado | `ocorrencias.py` |
| Assistente contextual (Gemini só reformula) | implementado; chamadas reais de amostra | `linguagem/`, `docs/validacao_gemini.md` |
| Painel (desktop) com mapa 3D e fallback 2D | implementado e testado em navegador | `app/static/` |
| PWA de navegação | implementada e testada em navegador | `app/static/pwa/` |
| Demonstração controlada e reproduzível | implementada; roteiro e teste de ponta a ponta | `make demo`, `docs/demonstracao.md`, `tests/e2e/jornada.js` |

## 3. Metodologia (resumo e onde está o detalhe)

- **Dados e proveniência:** `README.md` (fontes e atribuição), tela de Proveniência. Rede de ruas: OpenStreetMap (24/10/2026); relevo: Copernicus DEM; chuva: Open-Meteo (modelo, regional); eventos: 24 bloqueios da EPTC em 4 datas, 19 geocodificados; ocorrências oficiais do S2iD e bloqueios da CPRv BM no Rio Grande do Sul.
- **Processamento espacial:** segmentos viários com atributos físicos (cota, relevo local, declividade, altura sobre a água, fluxo, TWI); cobertura de dados calculada e declarada por território e modal (`docs/produto_preventivo.md`).
- **Meteorologia:** uma série horária para a cidade; passado recente é análise do modelo (não pluviômetro); validade de 6 h; sem dados, sem estimativa de risco (`docs/produto_preventivo.md`, seção Meteorologia).
- **Risco:** `escore = fator de chuva × peso do trecho`; fator ancorado nos níveis observados em dias com bloqueios; peso por rampa sobre o percentil do índice físico; classes Atenção ≥ 0,25 e Alto ≥ 0,60; parâmetros sem base marcados como provisórios e **não ajustados a ocorrências**.
- **Roteamento:** Dijkstra com custo = tempo + penalidade (risco × confiabilidade × aversão) avaliada no horário de passagem; interdição confirmada é bloqueio rígido.
- **Separação de conceitos** (como o produto a mantém): *suscetibilidade espacial* (índice físico, relativo), *previsão temporal* (só chuva futura e regra explícita) e *impacto na mobilidade* (rotas e simulação de fechamento). Nada disso é uma previsão de alagamento validada.

## 4. Resultados e como foram obtidos

| Resultado | Evidência | Leitura correta |
|---|---|---|
| O algoritmo de rotas devolve o caminho mínimo | 100 pares por modal contra networkx, **0 diferenças** (`reports/ml/rotas_auditoria.json`) | prova a **correção computacional** do algoritmo; não valida a qualidade da malha OSM nem o tempo real de viagem |
| Uma busca com corredor piorava rotas | uma rota a pé ficou 12 min pior; o corredor foi removido | achado da auditoria, corrigido |
| A interdição confirmada altera a rota | teste de ponta a ponta (`tests/e2e/jornada.js`): relato, confirmação do operador, traçado muda | demonstra o mecanismo, com **dados sintéticos** |
| O baseline detecta pouco os bloqueios documentados | 4 de 19 em algum horário do dia; 2 na hora do reporte; dos 15 não detectados, 9 têm peso zero, 6 tiveram chuva abaixo do nível que sinaliza o trecho (`reports/ml/risco_trecho_auditoria.json`) | **resultado negativo honesto**: o índice físico não discrimina bem esses locais |
| Nenhum corte do índice resolve | curva do corte no relatório; nenhum parâmetro foi alterado | falta poder discriminativo, e os eventos são poucos |
| 682 de 2.863 dias com alguma via em Atenção, só 4 dias com registro | `dias_de_alerta_sem_registro` | ausência de registro **não** é exemplo negativo |
| Suscetibilidade por ML (protótipo) | `reports/qa/susceptibility_run.json`: 207 segmentos positivos, 17 eventos; em blocos espaciais a regra de elevação baixa (mediana de percentil 0,80) fica ao lado do random forest (0,82); no teste temporal (9 eventos) os resultados divergem entre modelos | amostra pequena e viés de notificação: o protótipo ordena trechos por semelhança de terreno, **não prevê alagamento** |
| Suíte automatizada | ver `docs/qa_relatorio_final.md` | cobre lógica, contratos, HTTP, auditorias e navegador |

## 5. Conclusão

O que se pode afirmar: a plataforma **integra** dados territoriais, meteorologia, ocorrências com confirmação humana, roteamento e uma
camada de comunicação, de ponta a ponta, em ambiente controlado; o roteamento está correto computacionalmente; uma interdição confirmada
altera de fato as rotas; as limitações aparecem na interface, não só na documentação.

O que **não** se pode afirmar: que o sistema prevê alagamentos em vias, que uma rota é segura, que a chuva regional vale para uma rua, ou
que o desempenho vale fora das 4 datas e dos 19 pontos disponíveis. A pergunta de pesquisa sobre previsão viária **não foi respondida
afirmativamente**: a evidência é negativa ou inconclusiva, e esse é um resultado do trabalho, não uma falha de entrega.

**Hipótese da proposta.** A proposta supunha que um modelo treinado superaria regras simples. Com os dados disponíveis ela **não foi confirmada**: no teste temporal de
2025 (9 eventos) a regressão logística (percentil mediano 0,86) empata com a regra de terreno baixo (0,85) e o random forest sobreajusta (0,28). O estimador de
impacto (Modelo 2) **não foi treinado**; a perda de mobilidade é calculada por simulação de roteamento com regra explícita. A comparação completa entre o proposto e
o entregue está na seção 6 de `proposta.md` e na seção 10 da documentação técnica (`.docx`, ambos preservados e atualizados).

## 6. Limitações

Veja `docs/produto_preventivo.md` (limitações e pendências), `docs/seguranca_lgpd.md` e `docs/validacao_gemini.md`. Em resumo: dados de
eventos poucos e enviesados; chuva modelada e regional; sem ônibus; um processo e armazenamento em arquivo; assistente validado em amostra
pequena; sem teste em dispositivo físico; nada publicado.

## 7. Próximos dados necessários para validar a previsão viária

Ocorrências georreferenciadas em maior número e por mais datas (idealmente com hora e duração); chuva medida por pluviômetros ou radar com
resolução melhor que 10 km; rótulos de ausência verificados (dias com chuva forte e via livre); histórico de interdições do operador em uso
real. Só com isso uma calibração, e então um modelo temporal por trecho, seriam defensáveis.
