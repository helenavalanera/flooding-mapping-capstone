# Roadmap — Flooding Mapping (escopo estadual, RS)

Última atualização: 08/11/2026.

**Pergunta de pesquisa.** Em que medida atributos de relevo, hidrografia, precipitação e características rodoviárias explicam a suscetibilidade de trechos viários do Rio Grande do Sul à interdição por alagamento; e qual é a perda de mobilidade a pé, de ônibus e de carro associada à interdição de trechos críticos.

**Produto.** Cruzar a previsão de chuva das próximas 72 h com relevo, hidrografia e rede viária para indicar trechos comprometidos, em alerta ou com interdição provável, e estimar a perda de mobilidade por modo. A saída é um **ranking relativo de risco em classes**, não uma probabilidade calibrada.

## Direção do produto (decisão de 25/11/2026)

**Objetivo central.** Estimar onde a água tende a se acumular nas vias públicas diante de determinadas condições de precipitação. A saída esperada é um mapa de **propensão estimada ao acúmulo** por trecho viário, condicionado a um cenário de chuva. Não é profundidade, duração nem previsão de alagamento, e não será apresentado como estimativa hidráulica validada.

**Estado em 25/11/2026.** O produto entrega **exposição estimada**: fator de chuva (uma série regional, grade de ~10 km) vezes o peso do terreno por trecho. A chuva não varia no espaço, então ela escala o valor sem reordenar as ruas. O experimento de sensibilidade hidrológica ([relatório](sensibilidade_hidrologica.md), [robustez](robustez_espacial.md)) testou formulações simplificadas com chuva **uniforme** e não demonstrou ganho incremental sobre o índice atual; **não testou** o motor condicionado à chuva descrito acima.

| Componente atual | Papel nesta direção |
|---|---|
| Rede viária | Unidade espacial de análise |
| DEM e derivados (Copernicus GLO-30, DSM de ~30 m) | Base topográfica, com limite para o microrrelevo das vias |
| Índice atual | Baseline de exposição para comparação |
| Dados históricos (124 trechos, 2013–2014, sem hora nem chuva) | Referência inicial de validação, não validação de previsão |
| Experimentos de ML e de física simplificada | Evidência sobre os limites das formulações testadas |
| Camada de IA generativa | Interface de consulta e interpretação ([proposta](proposta_assistente_territorial.md)); nunca motor de cálculo |

**Etapas.**

1. **Estabilização:** auditoria, testes, documentação e apresentação da versão atual ([auditoria](auditoria_final_2026-11.md)).
2. **Evolução do motor:** estimativa de acúmulo condicionada à precipitação. Pode começar com chuva e relevo, com as limitações explícitas, sem esperar os dados urbanos.
3. **Qualificação dos dados:** chuva com distribuição espacial e temporal, relevo de melhor resolução, uso do solo e impermeabilização, drenagem e eventos datados.
4. **Validação:** confrontar as estimativas com ocorrências observadas; desempenho espacial e temporal, com previsão histórica arquivada se o objetivo for prever.
5. **Inteligência aplicada:** ML só com dados e hipótese verificável; IA generativa para consultas e explicações com fonte.

**Regras que valem para o motor novo.** Não inventar pesos nem coeficientes e apresentá-los como medidos; qualquer valor suposto vira cenário declarado. Cenários de chuva são experimentos, não categorias oficiais. Testar padrões espaciais e temporais diferentes, porque o mesmo acumulado em toda a cidade só muda a intensidade. O índice atual continua como baseline em todas as comparações.

### Fontes municipais e modelo de retenção (auditoria de 25/11/2026)

Auditoria de rede pluvial, bocas de lobo, casas de bomba, hidrografia, uso do solo (Profill 2022), MDT e risco CPRM: [auditoria](auditoria_fontes_drenagem_poa.md), [inventário e matriz de disponibilidade](inventario_fontes_poa.md), [viabilidade e proposta matemática](modelo_retencao_viabilidade.md). Conclusões que mudam o roadmap:

- **Nível 3 (hidráulico) não é viável hoje:** capacidade das bombas vazia em 100% dos registros, rede sem identificador nem nós, material em 7,7%, bocas sem relação com o trecho.
- **Nível 2 parcial é viável, com intervalos:** só 17,3% da área classificada tem coeficiente fundamentado (edificação e via pavimentada); o resto exige cenário declarado ou dados de solo.
- **Relevo:** o MDT 2010 (pixel de 1 m) existe como serviço e supera o Copernicus nos 334 marcos (erro médio de 0,77 m contra 2,18 m), mas não é validação independente, a licença não está confirmada e a exatidão vertical é maior que a profundidade das depressões de rua.
- **Etapa 3 (qualificação dos dados)** passa a ter lista objetiva: licença e lote do MDT, eventos datados com chuva, pedologia e declividade, capacidade de bombas e condutos, nível do Guaíba.
- **Fase 2 concluída em 25/11/2026 (integração de dados):** inventário de drenagem (rede pluvial nas três camadas, poços, bocas de lobo e casas de bomba) e uso do solo de toda a cidade (605.245 polígonos) processados, validados e versionados em `data/processed/`; áreas por classe na grade de 30 m do DEM; dois métodos de coeficientes separados e a estrutura `V = P x A x C / 1000` com unidades validadas. Resultados em [qualidade_dados_fase2.md](qualidade_dados_fase2.md). **Nada disso entra ainda na aplicação nem em modelo.** Decisões vigentes: MDT adiado (Copernicus GLO-30 segue), drenagem só como inventário, dois métodos de coeficientes, escopo em toda a cidade.
- **Cobertura dos coeficientes:** o Método 1 cobre 17,3% da área classificada (edificação e via pavimentada); 75,1% fica sem coeficiente fundamentado e 7,6% fica fora do cálculo de escoamento (área úmida e corpo hídrico). Cenários só com hipótese declarada.
- **Fase 3 implementada em 25/11/2026 (motor de contribuição potencial e indicador topográfico):** fluxo D8 como floresta (acúmulo exato, massa conservada, idêntico a `susceptibility.flow_accumulation` no DEM real), geração por célula em dois métodos separados, associação ao trecho viário só pelas células de chegada da pegada (sem dupla contagem) e indicador topográfico de preenchimento. Método e limites em [fase3_motor.md](fase3_motor.md); resultados em [fase3_resultados.md](fase3_resultados.md). Decisões aplicadas: trecho como unidade de apresentação e célula de 30 m como computacional, envelope sempre para jardins e passeios, preenchimento só como indicador.
- **O que a Fase 3 entrega e o que não entrega:** entrega volume potencial gerado e contribuição potencial associada ao trecho, em intervalos por pacote de coeficientes, com a cobertura a montante como grau de confiança. **Não** calcula volume efetivamente transportado, retido, profundidade nem duração (faltam infiltração, perdas, capacidade de drenagem, chuva no tempo e eventos datados). Comparação exploratória com os 124 trechos de 2013 a 2014: nenhum candidato atende o critério de 10% com intervalo acima de zero; a regra atual permanece.
- **Fase 4 implementada em 25/11/2026 (saídas da Fase 3 na aplicação):** camada "Escoamento potencial por trecho" no mapa de Porto Alegre, com tiles vetoriais e fragmentos por trecho gerados dos Parquets, seleção de pacote, limite e chuva de referência (as três execuções do motor), legendas por grandeza, painel do trecho e metodologia. Detalhes, desempenho e limites em [fase4_integracao.md](fase4_integracao.md). Ainda sem publicação: os 70 MB derivados ficam fora do Git.
- **Fase 4.1 (auditoria e desempenho, 25/11/2026):** troca de pacote no mapa 3D de 7,2 s para 1,5 s (camadas por propriedade, só a opacidade muda); visão geral abaixo do zoom 13 avaliada e **não adotada** (nenhuma agregação é ao mesmo tempo defensável e útil); inventário de drenagem integrado como camada contextual, fora do cálculo; comparação de R2, Pages e Render com recomendação (R2, aguardando decisão). Ver [fase41_auditoria.md](fase41_auditoria.md).
- **Landing científica (25/11/2026):** `/inicio/` redesenhada como apresentação editorial do estudo (nove seções, números rastreáveis, mapas e gráficos reais, resultado negativo em destaque, comparador de 10, 30 e 60 mm) e links que abrem o mapa já configurado. Gerada por `tools/gerar_landing.py` e testada; a apresentação do aplicativo do cidadão passou para `inicio/aplicativo.html`. Próximos da sequência: dashboard de resultados, mapa de análise, simulador, PWA, testes e migração para GitHub Pages + Releases. Ver [landing_estudo.md](landing_estudo.md).
- **Resultados executivos (25/11/2026):** aba Resultados do painel, em linguagem executiva e territorial, com quatro dimensões (urbanização, vegetação, topografia, drenagem), chuva de referência investigada (30 mm = percentil 75 dos totais por evento, 2017 a 2026, não a média), comparação de 10, 30 e 60 mm, síntese para decisão e registro de indicadores rastreáveis. Correção: os três pacotes de coeficientes cobrem classes diferentes, e os textos da landing foram ajustados. Ver [resultados_executivos.md](resultados_executivos.md).
- **Mapa de análise, simulador, PWA e preparação de publicação (26/11/2026):** painel do mapa organizado nas dimensões A a D (geração, contribuição, topografia, drenagem) sobre as camadas existentes; aba Simulador (10, 30 e 60 mm, sem motor próprio, valores iguais à saída do motor); aplicação de análise instalável com service worker de cache seletivo e aviso de cópia salva; página `inicio/celular.html` com a interface real em 390 px; URLs de dados configuráveis com conferência de hash; manifesto de publicação versionado e auditoria de integridade. Nada publicado. Detalhes, achados da auditoria e pendências (contraste, desempenho em aparelho físico, escolha de hospedagem dos dados): [`mapa_simulador_pwa.md`](mapa_simulador_pwa.md) e [`publicacao_pages_releases.md`](publicacao_pages_releases.md).
- **Consolidação final (26/11/2026):** cenários 10, 20 e 30 mm no lugar de 10, 30 e 60 (motor reexecutado; dados de base idênticos), textos oficiais das dimensões A a D, aviso de dados sintéticos separado das estimativas do estudo, modo claro permanente, narrativa institucional na landing, comparação Pages + Releases × Pages + R2 com CORS medido (assets de Releases sem CORS). Pendente, com autorização: implantação de teste no Pages (prazo de 10 min, `Range` do mapa-base), bucket de teste no R2 se necessário, medições em aparelho real e leitor de tela. Ver `docs/mapa_simulador_pwa.md` (seção 8) e `docs/publicacao_pages_releases.md`.
- **Fase 5, GeoAI (26/11/2026):** módulo experimental `src/flooding_mapping/geoai/` (Random Forest sobre Sentinel-2 L2A 2019 a 2021 e embeddings AlphaEarth 2020) que estima a fração construída por célula de 30 m. Validação espacial por blocos contra a Profill: MAE 0,049 (P1) e 0,052 (quadrante fora); AlphaEarth empata com o Random Forest (sem ganho); Prithvi documentado e não executado; sem validação independente nem teste de transferência. Classificação: **A, uso experimental**. Não alimenta o motor nem a interface. Ver `docs/geoai_fase5.md` e `docs/geoai_resultados.md`. Pendentes: validação independente, teste de transferência, seleção sazonal de cenas, licença da Profill, apresentação e proposta sem as Fases 3 a 5.
- **Aderência ao Capstone (26/11/2026):** matriz contra os requisitos oficiais em `docs/capstone_requisitos.md`: 2 dos 7 mínimos concluídos e 5 parciais (introdução, literatura do escopo atual, deploy das Fases 3 a 5, código aberto sem commit, apresentação). Dependem de autorização: commit, push e publicação.
- **Ordem sugerida a partir daqui:** (1) **feito para as saídas da Fase 3** (ver acima); falta exibir as camadas de inventário de drenagem, sempre com cenário, pacote, cobertura e limites visíveis; (2) pedir eventos datados com chuva associada, capacidade de bombas e condutos, e pedologia e declividade para fundamentar os coeficientes das classes sem referência; (3) chuva espacialmente distribuída, que o motor aceita como parâmetro; (4) volume efetivamente transportado só quando houver perdas, capacidade e condições de contorno; (5) retomar o MDT só se a decisão mudar.

## Arquitetura estadual

A malha oficial do DAER é a infraestrutura central: tudo o mais se pendura nos seus trechos.

```
DAER (planilha + ArcGIS)  →  trechos oficiais com atributos físicos e operacionais (código `codigo_sre`)
        ↓
Segmentação               →  segmentos analíticos de cerca de 1 km
        ↓
CRBM (coletor)            →  bloqueios associados aos segmentos (rodovia + km, conferidos com lat/lng)
        ↓
Dataset estadual          →  ocorrências + chuva + características do território
        ↓
Modelagem e validação     →  gatilho (município × dia) + suscetibilidade (segmento) + impacto de mobilidade
```

**Princípio metodológico.** Ter uma geometria para cada bloqueio não é ter histórico suficiente para treinar e validar um modelo estadual. O casamento espacial transforma cada bloqueio em dado utilizável; o volume só vem com o tempo de coleta. Até lá, o rótulo de trecho é escasso, e o gatilho (S2iD) é o modelo com base de verdade.

## Três frentes

| Frente | Conteúdo |
|---|---|
| **A. Infraestrutura geoespacial** | DAER (planilha e ArcGIS), segmentação, relevo, hidrografia |
| **B. Dados observacionais** | CRBM, S2iD, chuva e histórico municipal |
| **C. Modelagem** | dataset, gatilho, suscetibilidade, impacto e validação |

As três convergem no dataset estadual (item 9). Na prática o trabalho é sequencial, com uma exceção: a coleta (item 2) não espera ninguém.

## Ordem de execução

| # | Entrega | Frente | Prioridade | Situação |
|---|---|---|---|---|
| 1 | Atualizar o roadmap e registrar a arquitetura estadual | — | Alta | **Feito** |
| 2 | **Ativar o coletor da CRBM** e iniciar o histórico | B | Alta | **Ativo**: execuções agendadas e manual com sucesso. Falta: backup, permissão da CPRv BM |
| 3 | Ingestão da malha DAER (planilha + ArcGIS) | A | Alta | **Feito** (`ingestion/daer.py`; 1.683 trechos no ArcGIS, 1.686 na planilha) |
| 4 | Integrar atributos rodoviários por `codigo_sre` | A | Alta | **Feito**, com auditoria (5 junções aproximadas, 10 trechos sem planilha) |
| 5 | Subdividir os trechos em segmentos de cerca de 1 km | A | Alta | **Feito** (`geospatial/segments.py`; 20.450 segmentos) |
| 6 | Casar CRBM (rodovia + km → trecho/segmento), conferindo com lat/lng | A/B | Alta | **Feito** sobre os bloqueios ativos (17 de 17; 16 `ok`, 1 distante). Retroativo sobre o R2 implementado, **não executado** (sem credenciais locais) |
| 7 | Integrar relevo, hidrografia e demais variáveis físicas por segmento | A | Alta | **Feito** (Copernicus 30 m, OSM) |
| 8 | Consolidar a base municipal e temporal (S2iD + chuva) | B | Alta | **Feito** (S2iD 2017–2026; chuva ERA5 de 497 municípios, 3.593 dias) |
| 9 | Construir o dataset de treinamento do gatilho | C | Alta | **Feito** (`datasets/gatilho.py`) |
| 10 | Treinar e validar o gatilho | C | Alta | **Feito**; resultado e estado em `docs/ml_gatilho.md` |
| 11 | Construir o índice de suscetibilidade por segmento | C | Alta | **Feito** como índice físico relativo, **sem validação** em nível de segmento |
| 12 | Impacto de mobilidade: carro no RS (ponderado pelo VDM) e multimodal em Porto Alegre | C | Alta | **Feito** (simulado, RS); Porto Alegre preservado |
| 13 | Previsão de 72 horas | C | Média | **Feito** (`inference/forecast.py`) |
| 14 | Automatizar o processamento e a atualização | — | Média | Workflow `publicar-site` pronto; **não ativado** (precisa Pages e o modelo no R2; ver `docs/publicacao.md`) |
| 15 | Interface estadual | — | Posterior | **Feita** e testada localmente; publicação pendente da ativação |

Dependências que importam: o item 2 independe de todos; o 6 depende do 3 e do 5; o 9 depende dos 7 e 8; o 13 só começa depois de o 10 mostrar que o gatilho identifica eventos a partir da chuva.

## O que foi decidido e o que resta

**Resultados que mudaram o plano** (detalhes em `docs/ml_gatilho.md`):

- O gatilho municipal de aprendizado de máquina **não passou no portão** (três critérios independentes, medidos antes do teste). O gatilho em uso é a **regra de chuva relativa em 3 dias, calibrada**; o modelo fica registrado como experimental. A evidência é mista: antes do teste a regra foi melhor, e no teste de 2025–2026, com o mesmo número de dias em alerta, o modelo detectou mais eventos, dentro do ruído. Variações do modelo foram interrompidas para não ajustar o pipeline ao teste, que já foi consultado duas vezes (seção 8 do documento).
- O endpoint de "previsão histórica" do Open-Meteo devolve a **mesma série da reanálise**; previsões reais arquivadas existem só desde meados de 2024. A perda ao operar com previsão foi medida no teste.
- A suscetibilidade por segmento é um **índice físico relativo**, sem validação em nível de segmento (poucos rótulos). O impacto na mobilidade é **simulado**; o VDM cobre cerca de 38% dos segmentos e o ranking muda de verdade com o peso do tráfego.

**Pendências, todas dependentes de ação humana ou de credenciais:**

- [ ] **Publicar o site:** ativar o Pages com origem em Actions e enviar o modelo ao R2 (`docs/publicacao.md`). O workflow `publicar-site` está pronto e não foi executado.
- [ ] **Coletor:** confirmar com a CPRv BM que a coleta automatizada é permitida; fazer o backup mensal do bucket; acompanhar a cadência do `cron` (a primeira hora teve uma execução agendada).
- [ ] **Casamento retroativo dos bloqueios** sobre o histórico do R2: implementado (`--source r2`), não executado por falta de credenciais locais.
- [ ] **Licenças:** confirmar a licença dos dados do DAER antes de publicar derivados; decidir se o dataset do gatilho vai ao Zenodo ou ao Hugging Face.
- [ ] **Alertas de orçamento do R2** e e-mail de falha do GitHub (configuração no painel).
- [ ] **GTFS da EPTC** vencido em 12/12/2025: o ônibus em Porto Alegre representa a oferta daquele período.

**Para melhorar o gatilho (fora do escopo desta entrega):** mais episódios de rótulo (CRBM acumulando, mapas de inundação por satélite), rótulos no nível do trecho e chuva de maior resolução (radar), que é onde as tempestades locais perdidas aparecem.

## Corte de MVP (se o prazo apertar)
Itens 2 a 10 e 15 (versão enxuta), com carro no RS e multimodal pré-calculado só em Porto Alegre. Ficam como limitações declaradas: a classificação fina do texto da CRBM, o emulador de impacto validado, o GTFS atualizado e a previsão de 72 h.

## Riscos
1. **Poucos rótulos no nível do trecho:** a coleta só começa quando for ativada; nas primeiras semanas o volume é pequeno e mistura causas.
2. Eventos muito concentrados no S2iD e mudança de notificação a partir de 2023.
3. Diferença entre o treino (reanálise) e a operação (previsão).
4. VDM e IRI ausentes em cerca de 60% dos trechos.
5. GTFS vencido: o ônibus em tempo real não é confiável sem atualização.
6. Mudança nas regras de acesso da CRBM ou do WAF; o alerta de falha cobre a interrupção.
7. Limite gratuito do R2: mitigado pelos controles acima.
