# Resultados executivos (aba Resultados)

A aba **Resultados** do painel (`#poa/resultados`) é a leitura executiva e territorial do estudo, para gestores, planejamento urbano, pesquisa e organizações de infraestrutura. Pergunta orientadora: *dada uma precipitação de referência em Porto Alegre, quais contextos territoriais apresentam maior geração potencial de escoamento, concentração de contribuição e propensão topográfica à retenção?*

Os números vêm de `tools/gerar_resultados.py` (biblioteca `src/flooding_mapping/resultados.py`) para `static/data/resultados_poa.json` (121 KB). Nada é digitado à mão; cada afirmação conclusiva é um achado com uma **condição calculada**: se ela deixar de valer, o título muda para uma formulação neutra (`afirmacao(...)`, testado). Cada indicador (13) traz fórmula, unidade, fonte, cenário, método, cobertura e limitações, e o gerador recusa um indicador sem esses campos.

## 1. Chuva de referência: o que a investigação encontrou

Série diária de Porto Alegre, 2017-01-01 a 2026-11-02 (3.593 dias), do arquivo de reanálise do Open-Meteo (base ERA5; ponto da grade -30,123 / -51,203), já no cache da ingestão. É modelada, não pluviômetro; a grade suaviza e subestima extremos locais.

Tratamento: dia com chuva = 1 mm ou mais; **evento** = sequência de dias seguidos com chuva; total do evento = soma dos dias. Resultado: 618 eventos (62,8 por ano), duração média de 2,1 dias.

| Medida | Valor |
|---|---|
| Média anual (anos completos) | 1.449 mm por ano |
| Média mensal | 121 mm por mês |
| Média diária (todos os dias) | 4,0 mm por dia |
| Média por dia com chuva | 10,9 mm (36% dos dias) |
| Total por evento: média / mediana / percentil 75 / 90 / 95 / 99 | 22,8 / 12,7 / 29,9 / 53,2 / 78,4 / 142,1 mm |

**Decisão:** a referência operacional continua **30 mm**, e agora está situada: é o **percentil 75 dos totais por evento** (15,7 eventos por ano o igualam ou superam), e **não** a média histórica (22,8 mm por evento; mediana de 12,7 mm). 10 mm fica abaixo da mediana (percentil 43) e 20 mm é o percentil 62. Os três cenários (10, 20 e 30 mm) seguem para análise de sensibilidade. O cenário de 60 mm (percentil 92) foi retirado em 26/11/2026 por decisão de produto: o motor foi reexecutado com 10, 20 e 30 mm e os dados de base (células, trechos, tiles) saíram idênticos. Limite: o motor aplica o total como uniforme e sem tempo; um evento de dois dias não é uma chuva de 24 horas.

## 2. As quatro dimensões (podem se sobrepor)

- **A. Superfícies construídas e pavimentadas.** Edificação e vias pavimentadas somam 81,6 km² (17,3% da área classificada). Nas faixas mais impermeabilizadas o Método 1 estima mais escoamento por hectare (de 0,8 a 232 m³/ha a 30 mm). Essa relação vale **só para o Método 1** e é, em boa parte, consequência da definição do pacote; a analogia, que cobre outras classes, **não** é monotônica e por isso o título não a inclui. **Descoberta durante o trabalho:** os três pacotes cobrem **classes diferentes** (Método 1: edificação e via; analogia: vegetação e similares; limites físicos: as demais). Os totais "da cidade" por pacote são, então, os das classes de cada pacote, e a landing foi corrigida para dizer isso.
- **B. Vegetação e demais coberturas.** Distribuição das 15 classes e coeficientes por pacote; a maior parcela da incerteza da analogia (46% da largura do intervalo) está em *Jardins, Passeios ou Áreas semi urbanizadas*, classe sem coeficiente fundamentado.
- **C. Concentração do escoamento e propensão topográfica à retenção.** O trecho do percentil 99 recebe 1.323 vezes a contribuição da mediana. Contribuição acumulada e propensão topográfica são quase independentes (correlação de postos de 0,26): 59% dos trechos do décimo de maior contribuição têm algum preenchimento de depressão, contra 18% nos demais. Ranking de bairros por quantis e razões (nada somado entre trechos), só com 200 trechos com dados ou mais.
- **D. Drenagem cadastrada.** 2.961 km de rede, 88.860 poços, 44.761 bocas. Presença de elemento cadastrado perto dos trechos cresce com a contribuição (2% a 72% para bocas de lobo, do primeiro ao quinto quintil), mas a diferença reflete, em boa parte, **onde há cadastro**. Contexto apenas: sem capacidade, funcionamento, conectividade nem eficiência.

## 3. Comparação de cenários e síntese

Volumes e contagens sob 10, 20 e 30 mm: o volume sobe na proporção da chuva (fator 3 entre 10 e 30 mm, conferido por trecho contra a saída do motor), a ordem dos trechos não muda e as contagens de trechos acima de 100, 1.000 e 10.000 m³ mostram a sensibilidade. Nada disso indica profundidade, extensão ou duração de alagamento.

A síntese "O que esses resultados significam para o território?" lista contextos para investigação prioritária (**hipóteses**), as áreas de maior contribuição, as lacunas de dados, as limitações da drenagem e o que falta para uma análise hidráulica (eventos datados com chuva, capacidade e conexões da drenagem, pedologia e declividade, fração permeável de jardins, modelo de terreno mais fino, chuva no tempo e no espaço). Não afirma que o produto identifica pontos de alagamento confirmado.

## 4. Verificação

`tests/test_resultados.py` (15): recomputa a chuva da série em cache, os totais por pacote contra a soma das células e contra o relatório do motor, os quantis contra os Parquets, as áreas por classe contra o relatório de qualidade, a partição por faixa de impermeabilização, a coerência de cada título com os números, o requisito de rastreabilidade, a ausência de soma de contribuição entre trechos e de linguagem fora do que foi calculado. `tests/test_resultados_js.py` (6, Node) e `tests/e2e/resultados.js` (navegador, 360 a 1.280 px) conferem a estrutura executiva, a reescala pela chuva e o ranking por bairro.

## 5. Limites

Resultados por bairro usam o ponto médio do trecho e o centro da célula para atribuir o bairro. A série de chuva é de reanálise. A relação com a drenagem é espacial e descritiva. Os achados refletem a execução de 25/11/2026: ao regenerar os dados, rodar `tools/gerar_resultados.py` (os testes acusam divergência). Mapa de análise, simulador e PWA ainda não receberam o redesign da sequência.
