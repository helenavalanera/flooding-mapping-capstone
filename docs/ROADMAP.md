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
| 1 | Atualizar o roadmap e registrar a arquitetura estadual | — | Alta | **Feito** (este documento) |
| 2 | **Ativar o coletor da CRBM** e iniciar o histórico | B | Alta | Pronto e testado; **falta o merge na `main`** |
| 3 | Ingestão da malha DAER (planilha + ArcGIS) | A | Alta | Fonte identificada e testada |
| 4 | Integrar atributos rodoviários por `codigo_sre` | A | Alta | Viabilidade demonstrada |
| 5 | Subdividir os trechos em segmentos de cerca de 1 km | A | Alta | Pendente |
| 6 | Casar CRBM (rodovia + km → trecho/segmento), conferindo com lat/lng | A/B | Alta | Teste inicial: 17 de 17 |
| 7 | Integrar relevo, hidrografia e demais variáveis físicas por segmento | A | Alta | Pendente |
| 8 | Consolidar a base municipal e temporal (S2iD + chuva) | B | Alta | S2iD consolidado; falta a chuva |
| 9 | Construir o dataset de treinamento do gatilho | C | Alta | Pendente |
| 10 | Treinar e validar o gatilho | C | Alta | Pendente |
| 11 | Construir o índice de suscetibilidade por segmento | C | Alta | Pendente (sem rótulo de segmento ainda) |
| 12 | Impacto de mobilidade: carro no RS (ponderado pelo VDM) e multimodal em Porto Alegre | C | Alta | Só Porto Alegre |
| 13 | Previsão de 72 horas | C | Média | Pendente; só depois do item 10 |
| 14 | Automatizar o processamento e a atualização | — | Média | Pendente |
| 15 | Interface estadual | — | Posterior | Existe a versão de Porto Alegre |

Dependências que importam: o item 2 independe de todos; o 6 depende do 3 e do 5; o 9 depende dos 7 e 8; o 13 só começa depois de o 10 mostrar que o gatilho identifica eventos a partir da chuva.

## Detalhe por item

### 1 a 2 — Registro e coleta
- [x] Escopo estadual, pergunta de pesquisa e arquitetura registrados.
- [x] Repositório público; Cloudflare R2 e GitHub configurados (segredos cadastrados).
- [x] Coletor implementado (`collector.py`, `r2.py`, `.github/workflows/coletor-crbm.yml`), a cada 30 min, gravando só quando há mudança. Ver `docs/coletor_crbm.md`.
- [ ] **Colocar o workflow na `main`** (o `cron` só roda a partir da branch padrão) e fazer uma execução manual de teste.
- [ ] Confirmar o alerta de falha por e-mail (Settings → Notifications → Actions).
- [ ] Verificar se a CPRv BM permite a coleta automatizada.
- [ ] Backup mensal do histórico fora do R2.
- O casamento com o DAER **não bloqueia** a coleta: o registro guarda `rodovia`, `km` e `lat`/`lng`, e a associação pode ser feita depois, de forma retroativa.

### 3 a 5 — Malha DAER (frente A)
Fontes verificadas em 08/11/2026:
- **Planilha** (Relatório do SRE, consulta de 11/09/2026): 1.686 trechos, 525 rodovias, cerca de 19.161 km, 80 colunas. Revestimento, situação física e administração com 100% de preenchimento; **VDM** (tráfego médio diário) em 38% (638 trechos); **IRI** (irregularidade) de 2018, 2022 e 2025 em cerca de 40%; ano de pavimentação em 43%; área urbanizada em 258 trechos.
- **ArcGIS** (`iede.rs.gov.br/.../Rodovias_RS_por_Administracao/MapServer/0`): 1.683 trechos com geometria de linha, até 3.000 registros por consulta (uma única consulta basta) e o mesmo código `codigo_sre`.
- `mapa.daer.rs.gov.br` e `ogc.php` não responderam (timeout) a partir da máquina de análise; não são necessários.

Tarefas:
- [ ] Módulo de ingestão: baixa a camada ArcGIS e lê a planilha; junta por `codigo_sre`; registra a procedência no manifesto. O `.xls` (9 MB) fica em `data/raw/`, fora do git.
- [ ] Reconciliar as 3 diferenças entre a planilha (1.686) e o ArcGIS (1.683).
- [ ] Definir o tratamento do VDM e do IRI ausentes (omitir, imputar ou indicador "sem dado").
- [ ] Verificar a licença de uso dos dados do DAER antes de publicar derivados.
- [ ] Subdividir em segmentos de cerca de 1 km, com a posição do km interpolada ao longo da linha.
- **Pronto quando:** existe uma tabela de segmentos do RS, em Parquet, com geometria e atributos, e um teste valida o esquema e a junção.

### 6 — Casamento CRBM → DAER
- Teste inicial: 17 de 17 bloqueios ativos casaram por rodovia e faixa de km. Em 9 dos 17 o `km_fim` não vem (bloqueio pontual).
- [ ] Testar rodovias federais (`BR-` na CRBM contra `BRS-` no DAER), que ainda não apareceram nos bloqueios.
- [ ] Posicionar o bloqueio no segmento de 1 km e conferir com `lat`/`lng` (a distância entre os dois é uma medida de qualidade do casamento).
- [ ] Classificar o texto livre (`informacoes`) para separar alagamento de erosão e falha estrutural; o campo `climatico` não basta.
- **Pronto quando:** cada bloqueio arquivado tem trecho, segmento e uma medida de confiança do casamento.

### 7 — Relevo e hidrografia
- [ ] MDT Copernicus do RS (dezenas de blocos) e atributos por segmento: elevação, cota relativa, declividade, distância e altura à água, fluxo acumulado, TWI, densidade de drenagem.
- [ ] Reaproveitar o que já existe em `susceptibility.py`.

### 8 a 10 — Base municipal e gatilho
**S2iD consolidado:** 6.487 registros do RS (2017 a 2026, 497 municípios); relevantes (enxurrada, inundação, alagamento, chuvas intensas): 2.395 registros, 492 municípios, 479 datas, **136 episódios** independentes. Os dois maiores episódios concentram cerca de 40% dos registros (abr–mai/2024: 522; set–dez/2023: 492).
- [ ] **Validar a data do evento** (a data do protocolo coincidiu com o pico de chuva em dois casos de Porto Alegre em 2017; testar com uma amostra maior).
- [ ] Coordenadas dos 497 municípios (a partir da malha do IBGE) e chuva diária, com cache local; respeitar os limites de uso da API.
- [x] **Fonte de chuva do treino:** reanálise ERA5 (série longa). O endpoint de "previsão histórica" do Open-Meteo devolve a **mesma série da reanálise** (diferença de 0,00 mm/dia em 2019–2026), então não é um arquivo de previsões; previsões reais arquivadas existem só desde meados de 2024 (API de execuções anteriores). A perda ao operar com previsão é medida no teste (2025 em diante) em `reports/ml/skew_estrito.json`.
- [ ] Definir os códigos COBRADE do rótulo (12100, 12200, 12300; decidir sobre 13214 "Chuvas Intensas", que é ampla) e o uso do status (Reconhecido, Registro, Não reconhecido) como confiança.
- [ ] **Tratar a mudança de notificação a partir de 2023** (aumento de "Chuvas Intensas"), que pode confundir a validação no tempo.
- [ ] Avaliar as colunas de danos em obras de infraestrutura pública (58% dos relevantes têm valor): indício, não rótulo de trecho.
- [ ] Dataset município × dia (cerca de 1,8 milhão de linhas e 2.395 positivos, 1 para 750): métricas de ranking e validação **por episódio**.
- [ ] Transformar o script de consolidação do S2iD em módulo do projeto, com testes.
- **Pronto quando:** há métricas do gatilho por episódio e um relatório do que foi e do que não foi validado.

### 11 — Suscetibilidade por segmento
- Rótulos disponíveis: os 17 eventos de Porto Alegre (207 segmentos positivos), o histórico da CRBM que se acumula a partir da ativação e rótulos fracos do S2iD (município-evento).
- Resultado atual (Porto Alegre): o modelo logístico **não supera a regra simples "elevação baixa"** (validação espacial: percentil mediano 0,754 contra 0,797; temporal: 0,862 contra 0,853). A floresta aleatória fica abaixo do acaso na validação temporal.
- [ ] Apresentar como **índice explicável**, sempre comparado com a regra simples, sem prometer previsão.
- [ ] Testar se os rótulos fracos do S2iD melhoram o índice em validação por bacia ou por episódio.

### 12 — Impacto de mobilidade
- [ ] **Carro, RS:** eficiência da rede, maior componente conexa e população isolada, **ponderados pelo VDM** do trecho.
- [ ] **Multimodal, Porto Alegre:** r5py a pé, de ônibus e de carro.
- [ ] Atualizar o GTFS da EPTC (o último perdeu a vigência em 12/12/2025) ou declarar a limitação.
- [ ] Biblioteca de cenários pré-simulados e agregação rápida (emulador de impacto), validada contra o r5py.

### 13 a 15 — Previsão, automação e interface
- [ ] Previsão de 72 h em três janelas de 24 h, com a chuva antecedente; faixa de incerteza.
- [ ] Job agendado que gera um JSON estático; o dashboard apenas o lê. Em falha, manter a última saída válida e marcá-la como desatualizada.
- [ ] Interface: mapa do RS por janela, seleção de modo, ranking de 10 a 20 trechos, ficha do trecho, data da última atualização e aviso de que não substitui os alertas oficiais da Defesa Civil.

## Controle de custo do R2
Regras, orçamento e proteções em `docs/coletor_crbm.md`. Resumo: um único bucket; só `GetObject` e `PutObject`; nada de Infrequent Access; JSON público do dashboard fora do R2; alertas de orçamento em 50%, 80% e qualquer cobrança, **testados**; backup fora do R2.

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
