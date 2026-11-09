# Roadmap — Flooding Mapping (escopo estadual, RS)

Última atualização: 08/11/2026.

**Pergunta de pesquisa.** Em que medida atributos de relevo, hidrografia, precipitação e características rodoviárias explicam a suscetibilidade de trechos viários do Rio Grande do Sul à interdição por alagamento; e qual é a perda de mobilidade a pé, de ônibus e de carro associada à interdição de trechos críticos.

**Produto.** Cruzar a previsão de chuva das próximas 72 h com relevo, hidrografia e rede viária para indicar trechos comprometidos, em alerta ou com interdição provável, e estimar a perda de mobilidade por modo. A saída é um **ranking relativo de risco em classes**, não uma probabilidade calibrada.

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
