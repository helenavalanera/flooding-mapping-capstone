# Roteiro de apresentação do capstone

Gerado a partir das notas do apresentador de `docs/apresentacao/Flooding_Mapping_Capstone.pptx` (que `tools/gerar_apresentacao.py` produz). A duração usa 150 palavras por minuto (ritmo de fala corrido, com pausas curtas).
**Nenhuma regra de tempo ou de formato da banca foi fornecida; os tempos abaixo são uma estimativa ajustável, não um requisito institucional.**

Duração estimada do roteiro completo: **cerca de 12 minutos (12,3)**, sem perguntas.

## Versões

- **Completa (cerca de 12 min):** todos os slides, na ordem. Fica no limite superior de 8 a 12 minutos; se a banca fixar 12 minutos com perguntas, use a versão curta.
- **Curta (cerca de 9 min):** omita os slides 3 (problema e oportunidade), 5 (área de estudo), 7 (fontes), 8 (metodologia geoespacial), 13 (desktop) e 19 (contribuições), retomando a ideia de cada um em uma frase nos slides vizinhos.
- **Demonstração ao vivo:** se houver tempo, substitua os slides 13 e 14 por `make demo` e o roteiro de `docs/demonstracao.md` (cerca de 12 min à parte).

## Cuidados de honestidade (valem para qualquer versão)

- Capturas marcadas **SINTÉTICO** vêm da demonstração, com chuva e ocorrências inventadas; não são evidência de eventos reais.
- Os slides 14 e 17 dizem que o teste em aparelho físico está **pendente**. Se ele for feito antes da apresentação, atualize `docs/qa_mobile_fisico.md` e esses dois slides.
- Não diga que o sistema prevê alagamentos, que uma rota é segura ou que o modelo treinado superou as regras simples.

## Roteiro slide a slide

### Slide 1: Flooding Mapping (~23 s)

Boa tarde. Eu sou a Helena e vou apresentar o Flooding Mapping: uma plataforma que combina dados territoriais, meteorologia, ocorrências e roteamento para ajudar a entender como os alagamentos afetam a mobilidade em Porto Alegre. Vou mostrar o que foi construído, o que foi medido e, com a mesma ênfase, o que o trabalho não demonstra.

### Slide 2: A chuva que desorganiza a cidade não é só a extrema (~31 s)

Os alagamentos pluviais fecham cruzamentos e trechos de vias em Porto Alegre várias vezes por ano. O menor acumulado em 24 horas que já coincidiu com bloqueios registrados pela EPTC é 26,2 milímetros. Pela reanálise de 2015 a 2024, esse nível é igualado ou superado em média em 14 dias por ano, com variação de 8 a 21. Ou seja, chuvas comuns, não só eventos extremos, já desorganizam o deslocamento. Atenção: é dado modelado, não medição de pluviômetro.

### Slide 3: Problema e oportunidade (~30 s)

O problema tem duas camadas. Primeiro, o fenômeno: chuvas comuns bloqueiam vias. Segundo, a informação: os dados públicos são parciais. O GTFS de ônibus perdeu a vigência em dezembro de 2025; os bloqueios documentados são 24 pontos em 4 datas; não há dados abertos de bocas de lobo; a chuva disponível é modelada. A oportunidade é integrar o que existe, reprodutivelmente, e deixar explícito o que é observado, o que é estimado e o que falta.

### Slide 4: Objetivos do projeto (~36 s)

O objetivo geral da proposta era um modelo de aprendizado de máquina que estimasse a mobilidade perdida com chuvas de até 45 milímetros. Os objetivos específicos eram quatro. Três foram entregues, de forma completa ou como protótipo; o estimador de impacto, o chamado Modelo 2, não foi treinado: a perda é calculada por simulação de roteamento com regra explícita. A hipótese, de que um modelo treinado supera regras simples, não foi confirmada: a logística empata com a regra de terreno baixo, e o random forest sobreajusta. Isso é um resultado do trabalho.

### Slide 5: Área de estudo: Porto Alegre/RS (~36 s)

A área de estudo é Porto Alegre: 1 milhão 333 mil habitantes no Censo de 2022, e 176 mil segmentos de via no OpenStreetMap. A figura mostra a cidade alcançável: a parcela da população que uma pessoa alcança em 30 minutos, sem chuva, a pé, de carro e de ônibus, em uma grade de 1 quilômetro. Na plataforma, o Rio Grande do Sul entra como monitoramento regional, com 497 municípios e a malha de rodovias do DAER, mas rotas e risco por trecho existem só em Porto Alegre.

### Slide 6: Arquitetura da solução (~32 s)

A arquitetura é deliberadamente simples. À esquerda, as fontes de dados. No centro, um serviço de análise em Python, um único processo, que concentra as regras: meteorologia, risco por trecho, roteamento, ocorrências e interdições. À direita, o painel de análise para desktop e o aplicativo web para celular, ambos consumindo a mesma API. O assistente com Gemini reformula textos que o sistema já calculou; ele não calcula, não classifica e não cria interdições. Há também o operador humano, que confirma ocorrências.

### Slide 7: Fontes e integração dos dados (~26 s)

Todas as fontes são abertas. Para cada uma, a tabela diz o uso, a referência temporal e o limite. Destaco três: o GTFS está vencido; os eventos de bloqueio são poucos e enviesados pela notificação; e a chuva é modelada, em grade de cerca de 10 quilômetros. A plataforma mostra isso na tela de proveniência. A licença dos dados do DAER ainda precisa ser confirmada.

### Slide 8: Metodologia geoespacial (~38 s)

A medida central é a cidade alcançável: a população das células de uma grade de 1 quilômetro que se alcança em 30 minutos, a pé, de ônibus e de carro, calculada com o r5py. A mobilidade perdida compara essa população com e sem o fechamento de trechos. Os trechos que fecham vêm de uma regra explícita: abaixo de 26,2 milímetros nada fecha; a partir daí fecham os bloqueios documentados e alguns pontos que o modelo de suscetibilidade indica. Esse modelo ordena segmentos pela semelhança de terreno com os locais já bloqueados; ele não prevê alagamento.

### Slide 9: Meteorologia e suas limitações (~38 s)

A chuva do produto é uma única série horária para a cidade inteira, de uma grade de cerca de 10 quilômetros. O passado recente é análise do modelo, não medição de pluviômetro; as horas à frente são previsão. Os dados valem 6 horas. Se a fonte falhar, o último valor segue marcado como defasado até as 6 horas; depois disso o sistema diz que a chuva está indisponível, mostra só tempo e distância das rotas e avisa que isso não significa rota sem risco. A captura é da demonstração, com chuva sintética, e está identificada.

### Slide 10: Avaliação experimental de risco por trecho (~47 s)

O risco por trecho é um baseline determinístico: o escore é o fator de chuva vezes o peso do trecho, e o peso vem do percentil do índice físico do terreno. Eu o confrontei com os 19 bloqueios documentados. O resultado é honesto e negativo: o baseline sinalizou 4 dos 19 em algum horário do dia, e só 2 na hora do reporte. Nenhum corte do índice detecta os eventos sem sinalizar uma parcela grande da malha, então não há ajuste de parâmetro que resolva isso, e eu não ajustei nenhum. Também importa: em 2.863 dias, alguma via ficou em Atenção em 682, mas só 4 dias têm registro. Ausência de registro não é exemplo negativo.

### Slide 11: Roteamento e mobilidade (~38 s)

O roteamento usa o algoritmo de Dijkstra sobre a rede do OpenStreetMap. O custo é o tempo mais uma penalidade que depende do risco estimado no horário em que a pessoa passaria por cada trecho. Uma interdição confirmada remove o trecho do cálculo nos dois modais. Eu comparei o algoritmo com um caminho mínimo de referência, o NetworkX, em 100 pares por modal: nenhuma diferença. Isso valida o cálculo, não a qualidade da malha do OpenStreetMap nem o tempo real de viagem. Nenhuma rota é apresentada como segura: o produto fala em menor exposição estimada.

### Slide 12: Gestão de ocorrências e interdições (~37 s)

Este é o fluxo mais importante para a confiança do sistema. Qualquer pessoa pode relatar um problema, mas o relato entra como pendente e não interdita nada. Um operador, com credencial e evidência escrita, pode confirmar e declarar o impacto. Só a confirmação com impacto de interdição remove o trecho do cálculo das rotas. Tudo fica no histórico. O teste de ponta a ponta verifica que o traçado da rota muda depois da confirmação. Quem é o operador na prática, e quais evidências valem, depende de decisão institucional; está marcado como pendente de aprovação.

### Slide 13: Experiência desktop (~42 s)

O painel de análise tem o mapa como protagonista, com painéis flutuantes por cima. À esquerda, o Rio Grande do Sul, com a cobertura de dados dos municípios e a malha de rodovias. À direita, Porto Alegre, com o risco estimado por trecho em uma hora à frente, ocorrências e interdições, em 3D com relevo, que é só visual e não entra em nenhum cálculo. A captura de Porto Alegre usa chuva sintética e está identificada. Sem WebGL, o mapa 2D mantém as mesmas funções nos dois territórios. A aba de proveniência diz o que se pode e o que não se pode afirmar.

### Slide 14: Experiência PWA mobile (~36 s)

No celular, o mapa é a tela. No alto, um cartão de orientação com a rota e o que há adiante: a distância até o primeiro trecho de atenção e as interdições consideradas. Não há instruções de manobra, porque o backend não as produz. Uma barra lateral mostra onde a exposição estimada se concentra ao longo da rota. O painel inferior alterna entre resumo e detalhes por botão, sem depender de arrastar. As capturas são de emulação no Chromium e usam dados sintéticos; o teste em aparelho físico está pendente.

### Slide 15: Integração com o Gemini (~43 s)

O Gemini atua apenas como camada de comunicação. Cada pergunta sugerida tem uma resposta determinística montada a partir dos dados; o modelo só reformula. Ele não cria interdições, não altera ocorrências, não calcula rotas e não vê coordenadas. O texto que ele devolve passa por validação de tamanho e por um filtro que rejeita afirmações como 'rota segura'. Eu testei com chamadas reais em amostra pequena, com respostas entre 1,7 e 2,7 segundos, inclusive com uma instrução maliciosa na pergunta, que não criou nenhuma interdição. Não medi custo nem volume, e a chuva dessas chamadas era sintética. Sem a chave, o texto padrão funciona e a tela diz isso.

### Slide 16: Resultado do estudo de mobilidade (~42 s)

Este é o resultado central do estudo de pesquisa. Com chuva abaixo de 26,2 milímetros, nenhum bloqueio é atribuído. Entre 26 e 35 milímetros, a cidade perde 3,5 por cento da mobilidade de carro; com 40 a 45 milímetros, esse valor dobra para 7 por cento, atingindo 190 mil pessoas que perdem ao menos 10 por cento do que alcançam. A média esconde a instabilidade local: em algumas áreas a perda chega a 79 por cento. Atenção às ressalvas: o ajuste entre chuva e número de bloqueios usa só três datas, e os trechos fechados vêm de uma regra explícita, não de uma previsão validada.

### Slide 17: Resultados e testes (~36 s)

A suíte automatizada tem 500 testes aprovados e um ignorado, por falta de um pacote de publicação externa. Há cinco testes de navegador, incluindo a jornada integrada: relato, confirmação do operador e rota recalculada, e o mapa sem WebGL. O contêiner foi construído e validado, inclusive com chuva real e com a persistência após reinício. O roteamento foi conferido contra a referência. Cada linha tem uma leitura correta ao lado: por exemplo, os testes de navegador são em emulação, e a auditoria do roteamento valida o algoritmo, não a malha.

### Slide 18: Limitações e validade dos resultados (~37 s)

Esta é a lâmina que dá credibilidade ao resto. Não validamos a previsão de alagamento por rua: o baseline detectou 4 de 19 eventos. A chuva é regional, de cerca de 10 quilômetros, e o passado é análise de modelo. O roteamento está correto computacionalmente, mas isso não prova a malha. O Gemini foi testado em amostra pequena. Os dados sintéticos da demonstração não são validação empírica. Não houve teste em dispositivo físico, e nada foi publicado. E não declaramos conformidade com a LGPD: os controles técnicos existem, mas faltam base legal e processos.

### Slide 19: Contribuições do projeto (~29 s)

As contribuições não são uma previsão de alagamento, que não foi validada. São quatro. Primeiro, um pipeline reprodutível que mede a mobilidade perdida com dados abertos. Segundo, uma plataforma integrada, demonstrável de ponta a ponta. Terceiro, uma disciplina de transparência: cada resultado diz o que prova e o que não prova, e a interface separa observado, previsto, simulado e confirmado. Quarto, um resultado negativo documentado com rigor, que diz exatamente quais dados faltam.

### Slide 20: Conclusão (~31 s)

Concluindo. A pergunta sobre a perda de mobilidade com chuvas de até 45 milímetros foi respondida no estudo, com as ressalvas dos dados. O trabalho entregou uma ferramenta integrada, demonstrável e reproduzível, que mostra seus próprios limites. Mas é preciso ser claro: a hipótese de que um modelo treinado supera regras simples não foi confirmada, e a previsão de alagamento por trecho de via não foi validada. Isso não compromete a entrega; delimita o que ela afirma.

### Slide 21: Próximos passos (~29 s)

Os próximos passos são de dois tipos. Para validar a previsão por trecho, faltam dados: mais ocorrências georreferenciadas, por mais datas e com hora; chuva medida com resolução melhor que 10 quilômetros; rótulos de ausência verificados; e o histórico real de interdições confirmadas. Para pôr o produto em uso, faltam decisões e ações externas: o teste em dispositivo físico, a aprovação institucional do procedimento do operador e, só então, uma decisão separada sobre publicação.

## Perguntas prováveis e respostas curtas

- **O sistema prevê alagamentos?** Não. Ele estima exposição com um baseline explícito, que detectou 4 de 19 bloqueios documentados. Não está validado em vias.
- **Por que o modelo de aprendizado de máquina não é o gatilho em uso?** Porque não passou na margem de PR-AUC na validação (docs/ml_gatilho.md); a regra de chuva é o gatilho em uso.
- **A chuva é medida?** Não. É uma série regional de modelo, com grade de cerca de 10 km; o passado é análise de modelo.
- **O roteamento está validado?** O algoritmo, sim: 0 diferenças contra o NetworkX em 100 pares por modal. A qualidade da malha do OSM e o tempo real de viagem, não.
- **O que o Gemini faz?** Só reformula textos que o sistema já calculou. Sem a chave, há texto padrão. Foi testado em amostra pequena.
- **Os dados da demonstração são reais?** A rede de ruas é real; a chuva e as ocorrências da demonstração são sintéticas e identificadas.
- **E o ônibus?** Está no pipeline de pesquisa com o GTFS de 2025 (vencido), mas fora da plataforma.
- **Foi testado no celular?** Em emulação de navegador. O teste em aparelho físico está pendente (docs/qa_mobile_fisico.md).
