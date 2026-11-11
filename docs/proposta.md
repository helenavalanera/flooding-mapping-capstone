# Proposta de Projeto Final — Future Tech Leaders Brasil · Space Tech Bootcamp 2026 (estudo preliminar)

**Estimativa por aprendizado de máquina da perda de mobilidade urbana causada por alagamentos pluviais em Porto Alegre, sob dados públicos defasados**

**Candidata:** Helena de Oliveira Valanera — helena.valanera@gmail.com

**Repositório:** https://github.com/helenavalanera/flooding-mapping-capstone/tree/develop

## 1. Ideia do projeto

Os alagamentos pluviais interditam cruzamentos e trechos viários de Porto Alegre diversas vezes ao ano. Nos dias de chuva intensa, a Empresa Pública de Transporte e Circulação (EPTC) registra bloqueios totais e parciais por acúmulo de água que, em conjunto, alongam os deslocamentos e reduzem o acesso a diferentes partes da cidade. Evidência preliminar deste estudo indica que o menor acumulado em 24 horas associado a bloqueios registrados (26,2 mm, segundo chuva modelada, a mesma série da reanálise) é igualado ou superado, em média, em 14 dias por ano (totais diários de reanálise, 2015–2024); a instabilidade da mobilidade não decorre, portanto, apenas de eventos extremos. A quantificação desse efeito é limitada, contudo, por dados públicos parciais e defasados: o último feed GTFS publicado perdeu a vigência em 12/12/2025; os bloqueios documentados abrangem quatro datas entre 2019 e 2025 e estão sujeitos a viés de notificação; e não há dados abertos de bocas de lobo ou de limpeza urbana.

**Objetivo geral.** Desenvolver um modelo de aprendizado de máquina que estime o quanto a mobilidade urbana de Porto Alegre, a pé, de ônibus e de carro, é reduzida por chuvas de até 45 mm em 24 horas, a partir de atributos de relevo, drenagem e rede viária, e que possa ser reajustado quando dados atualizados estiverem disponíveis.

**Objetivos específicos.** (a) Mensurar a mobilidade de base, definida como a parcela da população do município alcançável em até 30 minutos, por modo de deslocamento; (b) estimar a suscetibilidade de cada trecho viário a bloqueios por acúmulo de água; (c) treinar e validar um estimador da mobilidade perdida por célula, modo e nível de chuva; (d) disponibilizar os resultados em cartografia e em painel de alerta alimentado pela previsão de chuva.

**Hipótese.** Atributos físicos do terreno e da rede viária explicam parte relevante da distribuição espacial da perda de mobilidade, de modo que um modelo treinado supera regras simples de decisão em validação espacial e temporal.

## 2. Relevância para os ODS e para o ecossistema espacial

O estudo contribui para o ODS 11 (metas 11.2 e 11.5), ao quantificar a perda de acesso a deslocamentos em desastres urbanos; para o ODS 13 (meta 13.1), ao relacionar chuvas frequentes à vulnerabilidade da cidade; e para o ODS 9 (meta 9.1), ao indicar trechos prioritários para uma infraestrutura resiliente. No ecossistema geoespacial, integra dados abertos (OpenStreetMap, GTFS, IBGE) e dados derivados de observação da Terra (modelo digital de elevação Copernicus), em procedimento reprodutível e replicável a outras cidades; a fase 2 incorpora imagens de radar Sentinel-1. A aplicação prática é a priorização de obras de drenagem e de desvios e a antecipação de trechos e linhas de ônibus expostos.

## 3. Exemplos de literatura

Estudos de acessibilidade sob inundação combinam simulação de inundação e análise de redes. Coles et al. (2017) acoplaram um modelo hidrodinâmico a análises de rede para avaliar o acesso de serviços de emergência em York (Reino Unido), e Green et al. (2017) mostraram, em Leicester, que o alagamento superficial prejudica o deslocamento das equipes de emergência mais do que a cheia fluvial de magnitude semelhante. Pregnolato et al. (2017) relacionaram a profundidade da água à velocidade do tráfego, e Latora e Marchiori (2001) propuseram a eficiência global de redes, adotada aqui como medida de robustez. O roteamento multimodal é realizado com o r5py (Fink et al., 2022). Esses trabalhos pressupõem simulações ou cenários detalhados de inundação, cuja base não foi localizada em dados abertos para Porto Alegre; a presente proposta difere ao empregar aprendizado de máquina treinado com dados abertos esparsos.

- COLES, D. et al. Beyond “flood hotspots”: modelling emergency service accessibility during flooding in York, UK. Journal of Hydrology, v. 546, p. 419–436, 2017. doi:10.1016/j.jhydrol.2016.12.013.
- GREEN, D. et al. City-scale accessibility of emergency responders operating during flood events. Natural Hazards and Earth System Sciences, v. 17, p. 1–16, 2017. doi:10.5194/nhess-17-1-2017.
- PREGNOLATO, M. et al. The impact of flooding on road transport: a depth-disruption function. Transportation Research Part D, v. 55, p. 67–81, 2017. doi:10.1016/j.trd.2017.06.020.
- LATORA, V.; MARCHIORI, M. Efficient behavior of small-world networks. Physical Review Letters, v. 87, 198701, 2001. doi:10.1103/PhysRevLett.87.198701.
- FINK, C. et al. r5py: Rapid Realistic Routing with R5 in Python. Zenodo, 2022. doi:10.5281/zenodo.7060438.

## 4. Dados

Os dados são abertos e apresentam defasagens que motivam a abordagem proposta (Tabela 1).

Tabela 1 — Fontes de dados, situação atual e defasagem.

| Dado | Fonte e formato | Defasagem ou lacuna |
|---|---|---|
| Ônibus | GTFS da EPTC (ZIP/CSV), vigência até 12/12/2025 | Cerca de 10 meses vencido; único publicado |
| Vias e drenagem | OpenStreetMap, 24/10/2026 (PBF): 176.836 segmentos | Sem bocas de lobo nem microdrenagem |
| População | IBGE, Censo 2022, setores (GPKG): 1.332.845 pessoas | Quatro anos; densidade uniforme no setor |
| Relevo | Copernicus DEM 30 m (GeoTIFF) | Superfície; sem meio-fio nem microrrelevo |
| Bloqueios | EPTC: 24 pontos em 4 datas (2019–2025), 19 geocodificados (CSV) | Amostra pequena, viés de notificação |
| Chuva | Open-Meteo: previsão, arquivo e reanálise 2015–2024 (JSON) | Dado modelado; não captou 06/03/2022 |

**Evidências preliminares.** Sem chuva, uma célula alcança em 30 minutos, em média, 80% da população do município de carro, 14% de ônibus e 2,7% a pé. Com o fechamento dos pontos documentados e de trechos indicados por um modelo de terreno, a mobilidade de carro da cidade reduz-se em 3,5% com 26–35 mm e em 7,0% com 40–45 mm (190 mil pessoas perdem ao menos 10% do que alcançam), com perdas locais de até 79%. Esse modelo, treinado com 17 locais, posiciona os eventos de 2025, não vistos no treino, no percentil mediano 0,86 da ordenação dos trechos, empatando com a regra “terreno mais baixo” (0,85).

## 5. Metodologia (machine learning)

**Mobilidade de base e perda.** Para cada célula de uma grade de 1 km (579 com população, alocada por densidade uniforme nos setores censitários), calcula-se com o r5py (versão 1.1.7) a população das células alcançáveis em até 30 minutos (partida às 07:00 de 30/10/2025, janela de 60 minutos, mediana dos tempos), a pé, de ônibus e de carro (A0). A mobilidade perdida na cidade é M = 1 − Σ(pi · As,i) / Σ(pi · A0,i), em que pi é a população da origem i e As,i, o valor após o fechamento de trechos; a instabilidade local é o maior (A0 − As)/A0 entre as origens.

**Da chuva ao fechamento.** Por regra explícita, abaixo de 26,2 mm em 24 h nenhum trecho fecha; a partir desse limiar fecham os pontos documentados e N pontos adicionais indicados pelo modelo de suscetibilidade, com N obtido por ajuste linear entre o acumulado e o número de bloqueios por data (três datas) e multiplicado por um fator de precariedade da drenagem (1 a 3).

**Modelo 1 — suscetibilidade (protótipo).** Regressão logística regularizada e random forest ordenam os 107.869 segmentos viários pela semelhança de terreno com os locais interditados (positivos e não rotulados), com atributos de elevação, declividade, escoamento (acúmulo de fluxo D8 e índice topográfico de umidade) e drenagem (distância e densidade de cursos d’água).

**Modelo 2 — estimador de impacto (a treinar).** Um modelo de gradient boosting, com regressão regularizada como linha de base, aprenderá a prever a mobilidade perdida por célula e modo a partir da chuva, da suscetibilidade dos trechos vizinhos, da conectividade e redundância de rotas, da acessibilidade de base e da população. Os rótulos serão obtidos por simulações de roteamento com conjuntos variados de trechos fechados, amostrados segundo a suscetibilidade (hoje há seis conjuntos distintos; cada simulação leva cerca de 3 minutos).

**Validação, incerteza e atualização.** Como os rótulos do Modelo 2 provêm da simulação, a validação excluirá níveis de chuva e blocos espaciais de 2 km, será avaliada pelo erro absoluto médio (pontos percentuais), pela correlação de Spearman por célula e pelo percentil mediano dos eventos reais, e será confrontada com regras simples e, quando disponíveis, com GTFS e eventos atualizados. A incerteza decorrerá da sensibilidade ao fator de precariedade. Na fase 2, uma rede U-Net aplicada a imagens Sentinel-1 rotulará áreas alagadas e ampliará os eventos.

**Justificativa.** Com poucos eventos, sem registros de chuva sem bloqueio e com dados defasados, regras fixas envelhecem rapidamente; um modelo treinado pode ser reajustado com dados novos e permite medir o ganho sobre regras simples. O aprendizado profundo só se justifica quando houver rótulos em escala. **Limitações.** Ajuste com três datas; GTFS de 2025; bloqueio binário; viés de notificação; temporais curtos podem fechar vias abaixo de 26 mm; o alerta é um nível heurístico, não uma probabilidade, e cobre apenas Porto Alegre.

## 6. Atualização do escopo e estado final (11/11/2026)

Esta seção foi acrescentada à proposta submetida. As seções 1 a 5 permanecem como foram escritas, porque registram o problema, a hipótese e o plano originais. O que segue diz o que foi entregue, o que mudou e o que não foi demonstrado.

_Tabela 2 — Proposta e situação final._

| Item proposto | Situação final | Evidência |
|---|---|---|
| (a) Mobilidade de base por modo (a pé, ônibus, carro) | Entregue no pipeline de pesquisa para Porto Alegre. O ônibus usa o GTFS vencido de 2025 | reports/qa/mobility_run.json; Documentação, seção 6 |
| (b) Suscetibilidade por trecho viário | Entregue como protótipo e como índice físico relativo. Sem validação em vias | reports/qa/susceptibility_run.json; reports/ml/risco_trecho_auditoria.json |
| (c) Estimador da mobilidade perdida (Modelo 2, gradient boosting) | Não treinado. A perda é calculada por simulação de roteamento com regra explícita; o estimador fica como trabalho futuro | ausente do repositório |
| (d) Cartografia e painel de alerta com a previsão de chuva | Entregue e ampliado: mapa interativo, painel e aplicativo web de navegação (PWA) para Porto Alegre, com monitoramento regional do Rio Grande do Sul | docs/produto_preventivo.md |
| Hipótese: um modelo treinado supera regras simples | Não confirmada. A regressão logística (percentil 0,86) empata com a regra de terreno baixo (0,85) no teste temporal de 2025, com poucos eventos; o random forest sobreajusta (0,28) | Documentação, seção 6.4 |
| Fase 2: U-Net com imagens Sentinel-1 | Não realizada | — |

**O que foi entregue.** Além do pipeline de pesquisa de Porto Alegre, o trabalho produziu (i) um gatilho municipal de risco hídrico para o Rio Grande do Sul (1.768.598 dias-município de 497 municípios, 99 episódios), no qual a regra de chuva é o gatilho em uso e o modelo de aprendizado de máquina permanece experimental, porque não passa na margem de PR-AUC na validação (docs/ml_gatilho.md); (ii) um serviço de análise para Porto Alegre, com roteamento de carro e a pé, meteorologia horária, ocorrências com confirmação humana e interdições; e (iii) um painel para análise e um aplicativo web (PWA) para quem vai se deslocar. Um provedor de linguagem (Gemini) apenas reformula textos que o sistema já calculou: não calcula, não classifica e não cria interdições.

**Três conceitos que o produto mantém separados.** A suscetibilidade espacial é o índice físico do terreno, relativo e não uma probabilidade. A previsão temporal usa apenas a chuva futura e uma regra explícita. O impacto na mobilidade é o efeito de fechar trechos nas rotas e na cidade alcançável. O produto não afirma que prevê alagamentos por rua.

**Resultados da auditoria.** O algoritmo de roteamento coincidiu com um caminho mínimo de referência (NetworkX) em 100 pares reais por modal, sem diferenças; isso valida o cálculo, não a qualidade da malha viária. O baseline de risco por trecho sinalizou 4 dos 19 bloqueios documentados em algum horário do dia e 2 na hora do reporte, e nenhum ajuste de parâmetro resolve essa baixa detecção sem sinalizar uma parcela grande da malha. Dias sinalizados sem registro não são falsos alertas comprovados: ausência de registro não é exemplo negativo (reports/ml/risco_trecho_auditoria.json).

**Limites de validade.** A chuva usada pelo produto é uma série regional, com grade de cerca de 10 km, e o passado recente é análise de modelo, não medição de pluviômetro. A integração com o Gemini foi testada em chamadas reais de amostra pequena, com chuva sintética. Dados sintéticos (chuva inventada e ocorrências de demonstração) foram usados apenas em testes e na demonstração, sempre identificados, e não constituem validação empírica. O produto não foi testado em dispositivo físico e não foi publicado.

**Conclusão.** A pergunta de pesquisa sobre a perda de mobilidade com chuvas de até 45 mm foi respondida no estudo preliminar, com as ressalvas dos dados. O trabalho entregou uma ferramenta integrada, demonstrável e reproduzível. A hipótese de que um modelo treinado supera regras simples não foi confirmada, e a previsão de alagamento por trecho viário não foi validada. Para validá-la faltam mais ocorrências georreferenciadas e por mais datas, chuva medida com resolução melhor que 10 km, rótulos de ausência verificados e o histórico de interdições confirmadas em uso real. Critérios de avaliação e formato exigidos pela instituição não foram fornecidos e não foram assumidos.
