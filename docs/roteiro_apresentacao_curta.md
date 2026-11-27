# Roteiro da apresentação curta (template FTL)

Gerado por `tools/gerar_apresentacao_ftl.py`, a partir do mesmo texto dos slides e das notas do apresentador do `.pptx`. Fala a 150 palavras por minuto.

Duração estimada da fala dos slides 3 a 12: **cerca de 7,4 min**, além de capa e encerramento.

## Slide 3: Por que isto importa para Porto Alegre (~40 s)

**No slide**

- Chuva comum já fecha ruas na cidade: o menor acumulado em 24 h associado a bloqueios da EPTC é 26,2 mm, e isso se repete em média 14 dias por ano.
- Falta um número para decidir: quanto acesso a cidade perde quando isso acontece, e onde. Sem ele, desvios, alertas e obras ficam sem medida.

**Fala**

Porto Alegre sabe que alaga. O que a cidade não tem é uma medida de quanto isso custa em deslocamento. O menor acumulado de chuva em 24 horas que já coincidiu com bloqueios registrados pela EPTC é 26,2 milímetros, e, pela reanálise de 2015 a 2024, esse nível é igualado ou superado em média em 14 dias por ano. Ou seja, não é só evento extremo. Quando isso acontece, quem decide um desvio, um alerta ou uma obra de drenagem faz isso sem saber quanta gente perde acesso e em quais áreas. Essa é a lacuna que o projeto ataca.

## Slide 4: Propósito e valor para a cidade (~48 s)

**No slide**

- Propósito: uma plataforma para quem mora na cidade, que mostra o que a chuva pode afetar perto de cada pessoa e aprende com o que a comunidade confirma.

**Fala**

O propósito do Flooding Mapping é ser uma plataforma para o cidadão, não mais uma ferramenta de gestão. Quem sai de casa vê se as ruas ao redor dos lugares que salvou entram em exposição estimada nas próximas horas, com os hospitais e escolas que ficam dentro de cada área. Quem viu uma rua alagada diz se ainda está alagado ou se já secou, e esse apoio ajuda a priorizar onde verificar primeiro, sem interditar rua nenhuma. E quem cuida da cidade enxerga, com a mesma informação aberta, onde a perda de acesso é maior, com áreas em que chega a 79 por cento. Esse é o valor potencial do desenho; eu não validei o uso com moradores nem com órgãos

## Slide 5: Como funciona: da chuva à decisão (~46 s)

**No slide**

- Seis etapas, cada uma dizendo o que é observado, estimado ou confirmado por gente. O apoio da comunidade nunca interdita uma via.

**Fala**

O caminho é este. Entram a chuva, com previsão horária e histórico, e o terreno e as ruas. Uma regra explícita define que nada fecha abaixo de 26,2 milímetros. Os trechos em exposição se juntam em áreas, que são cruzadas com 1.720 pontos de interesse do OpenStreetMap e com os lugares que a pessoa salvou. A comunidade confirma ou diz que secou, e cada confirmação vira um rótulo. Com isso o sistema aprende e sugere onde verificar primeiro, mas só troca a regra de terreno por um modelo se ele mostrar ganho em validação por blocos espaciais. É um ranking de prioridade, não uma previsão de alagamento, e nenhuma rota é apresentada como segura

## Slide 6: Relação com os ODS (~29 s)

**No slide**

- ODS 11, Cidades e comunidades sustentáveis (metas 11.2 e 11.5): quantifica a perda de acesso a deslocamentos em desastres urbanos.
- ODS 13, Ação contra a mudança do clima (meta 13.1): relaciona chuvas frequentes à vulnerabilidade da cidade.
- ODS 9, Indústria, inovação e infraestrutura (meta 9.1): aponta onde uma infraestrutura resiliente traria mais ganho de acesso.

**Fala**

O projeto se relaciona com três ODS. O 11, cidades sustentáveis, nas metas 11.2 e 11.5: ele mede a perda de acesso a deslocamentos em desastres urbanos. O 13, ação climática, na meta 13.1: ele relaciona chuvas frequentes à vulnerabilidade da cidade. E o 9, infraestrutura resiliente, na meta 9.1: ele indica onde uma obra traria mais ganho de acesso. A contribuição é de informação para a decisão, não uma solução de engenharia.

## Slide 7: Metodologia e dados (~39 s)

**No slide**

- Dados abertos: OpenStreetMap (176 mil trechos), Censo IBGE 2022, relevo Copernicus GLO-30 (DSM de ~30 m), GTFS de Porto Alegre, bloqueios da EPTC e chuva de reanálise (grade de ~10 km).
- Mobilidade perdida: população alcançável em 30 min (r5py), a pé, de ônibus e de carro, com e sem trechos fechados.
- Trechos fechados por regra explícita: nada abaixo de 26,2 mm; acima, os bloqueios documentados e pontos de maior suscetibilidade do terreno.
- Avisos e laço: bolsões de exposição com 1.720 pontos de interesse do OpenStreetMap; relatos apoiados pela comunidade viram rótulos para um modelo que só substitui a regra se mostrar ganho.

**Fala**

Todas as fontes são abertas: OpenStreetMap, Censo do IBGE, relevo do Copernicus, o GTFS de Porto Alegre, os bloqueios da EPTC e a chuva de reanálise, em grade de cerca de 10 quilômetros. A medida central é a população que se alcança em 30 minutos, calculada com o r5py. A mobilidade perdida é a diferença entre a cidade com e sem os trechos fechados, e os trechos fechados vêm de uma regra explícita, não de um modelo treinado. A tela de proveniência da plataforma diz, para cada informação, de onde vem e o que não se pode afirmar.

## Slide 8: Resultados: quanto a cidade perde (~36 s)

**No slide**

- Abaixo de 26,2 mm: nenhum bloqueio atribuído.
- De 26 a 35 mm, a cidade perde 3,5% da mobilidade de carro; de 40 a 45 mm o valor dobra, para 7%, e 190 mil pessoas perdem ao menos 10% do que alcançam.
- A média esconde o local: em algumas áreas a perda chega a 79%.
- Ressalva: o ajuste chuva-bloqueios usa só 3 datas.

**Fala**

O resultado central: com chuva abaixo de 26,2 milímetros, nenhum bloqueio é atribuído. Entre 26 e 35 milímetros, a cidade perde 3,5 por cento da mobilidade de carro. Entre 40 e 45, o valor dobra, para 7 por cento, e 190 mil pessoas perdem ao menos 10 por cento do que alcançam. A média esconde o local: em algumas áreas a perda chega a 79 por cento, e é isso que ajuda a priorizar. A ressalva é que o ajuste entre chuva e número de bloqueios usa só três datas.

## Slide 9: Validação: o que os dados permitem afirmar (~60 s)

**No slide**

- Altitude: o Copernicus GLO-30 é um DSM de ~30 m (inclui prédios e árvores; sem meio-fio nem microrrelevo). Contra 282 marcos da Prefeitura, a ordem das cotas bate (Spearman 0,99) com viés de +2,1 m: serve para ordenar trechos, não para medir a cota da rua.
- Terreno contra 124 trechos alagados registrados pela Prefeitura (2013–2014): AUC 0,666 e precisão média 0,00205, com taxa base de 0,115%. Sinal real, porém modesto.
- Esses registros não têm data, hora nem chuva: não validam previsão. A validação é espacial, por blocos, com intervalos de confiança; a decisão não mudou ao variar o tamanho dos blocos, a origem da grade e ao retirar blocos.
- Conceitos distintos: suscetibilidade do terreno (fixa), exposição estimada (terreno e chuva prevista), ocorrência observada (relato ou registro) e previsão de alagamento, que o produto não oferece.

**Fala**

Antes de mostrar o que testamos, o que os dados permitem afirmar. O relevo vem do Copernicus GLO-30, um modelo de superfície de cerca de 30 metros: enxerga prédios e árvores e não enxerga meio-fio nem sarjeta. Contra 282 marcos geodésicos da Prefeitura, a ordem das altitudes bate, correlação 0,99, mas com viés de 2,1 metros. Então serve para ordenar trechos, não para medir a cota da rua. Contra 124 trechos que a Prefeitura registrou como alagados em 2013 e 2014, o índice de terreno tem AUC 0,666: um sinal real, mas modesto. Esses registros não têm data, hora nem chuva, então não validam previsão. Por isso usamos validação espacial por blocos, com intervalos de confiança. E é importante separar quatro coisas: a suscetibilidade do terreno, que é fixa; a exposição estimada, que junta terreno e chuva prevista; a ocorrência observada; e a previsão de alagamento, que o produto não oferece.

## Slide 10: Experimento complementar: modelagem hidrológica (~53 s)

**No slide**

- Testamos fluxo acumulado, declividade, chuva uniforme (10, 30 e 60 mm) e coeficientes de escoamento hipotéticos contra a regra atual, nos mesmos 124 trechos, com validação por blocos espaciais.
- Resultado: nenhuma formulação atingiu o critério de adoção (ganho de 10% com intervalo de confiança acima de zero). Decisão: manter a regra e priorizar ocorrências datadas com chuva associada.

**Fala**

Também testamos se uma formulação física simplificada acrescentava informação à regra atual: fluxo acumulado ajustado pela declividade, com chuva uniforme de 10, 30 e 60 milímetros e coeficientes de escoamento hipotéticos. Comparamos nos mesmos 124 trechos, com validação por blocos espaciais. Nenhuma formulação atingiu o critério de adoção, que exige ganho de 10% com o intervalo de confiança acima de zero. A média de postos entre a regra e a física ficou um pouco acima, mas com intervalo muito largo: é uma hipótese, não uma evidência. Chuva uniforme não diferencia ruas: ela só escala o volume. O que comprovamos é restrito: as formulações simplificadas testadas não demonstraram ganho incremental com os dados disponíveis; não que a física não ajude. A decisão é manter a regra e priorizar ocorrências datadas, com chuva associada.

## Slide 11: A plataforma em uso (~47 s)

**No slide**

- Aba Avisos: as ruas ao redor dos lugares salvos, hora a hora, e as áreas em exposição com os pontos de interesse dentro.
- O laço: relatos que a comunidade confirma ou diz que secaram, e áreas sugeridas para verificar, com a fonte (regra ou modelo) à vista.
- Privacidade: lugares enviados sem nome e sem registro; apoio guardado só como código irreversível; sem rastreamento nem notificação.

**Fala**

Isso está entregue no aplicativo para o celular. A aba Avisos mostra, para os lugares que a pessoa salvou, a exposição estimada hora a hora, e as áreas em exposição com os pontos de interesse dentro delas. O laço da comunidade permite confirmar ou dizer que secou, e há uma lista de áreas sugeridas para verificar, que diz se a fonte é a regra de terreno ou o modelo aprendido. Na demonstração o modelo não superou a regra, e a tela diz isso. Os lugares vão ao servidor sem nome e sem registro, o apoio é guardado só como código irreversível, e não há rastreamento nem notificação. As telas usam chuva e relatos sintéticos e estão identificadas.

## Slide 12: Conclusão: valor entregue e o que falta (~48 s)

**No slide**

- Valor entregue: uma plataforma para o cidadão, com avisos por lugar, áreas e pontos de interesse afetados, e um laço em que a comunidade confirma; a cidade ganha uma medida da perda (3,5% a 7% do carro; até 79% em áreas).
- Limites: o baseline detectou 4 de 19 bloqueios em algum horário do dia (2 na hora do relato); o terreno tem sinal modesto e nem o modelo treinado nem a física simplificada superaram a regra; os relatos têm o viés de quem reporta; sem teste em celular físico nem com moradores.
- Próximos passos: um piloto com moradores para gerar confirmações reais, chuva medida em resolução melhor que 10 km, e renda do Censo para medir equidade.

**Fala**

Concluindo. O valor entregue é que a cidade passa a ter uma medida: de 3,5 a 7 por cento da mobilidade de carro perdida com chuvas de até 45 milímetros, e até 79 por cento em algumas áreas, junto com uma ferramenta que leva isso à decisão. Os limites precisam ficar claros: o baseline de risco por trecho detectou 4 de 19 bloqueios em algum horário do dia, e só 2 na hora do relato, um modelo treinado não superou regras simples, e não houve teste em celular físico nem validação com os órgãos. Por isso o próximo passo é mais dados, com ocorrências georreferenciadas e chuva medida, e um piloto com a Defesa Civil e a EPTC. Obrigada.

## Cuidados de honestidade

- As telas marcadas SINTÉTICO vêm da demonstração (chuva e ocorrências inventadas); não são evidência de eventos reais.
- O valor para Defesa Civil, EPTC, planejamento e cidadãos é o valor potencial do desenho; não houve validação de uso com esses públicos.
- Não dizer que o sistema prevê alagamentos, que uma rota é segura ou que o modelo treinado superou as regras simples.
