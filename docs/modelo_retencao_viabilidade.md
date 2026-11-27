# Viabilidade do modelo de acúmulo superficial: o que os dados sustentam

Estado: **diagnóstico e proposta**, em 25/11/2026. **Nenhum modelo de retenção foi implementado.** Base: [auditoria das fontes](auditoria_fontes_drenagem_poa.md) e [inventário](inventario_fontes_poa.md).

A pergunta do projeto é: *dada determinada chuva, onde a água tende a ficar retida, por quanto tempo e em que quantidade?* Os dados atuais permitem responder uma parte do **onde** e do **quanto chega**, com intervalos. **Não permitem** responder **por quanto tempo** nem **quanto fica retida**.

## 1. Decisão técnica

**Dados efetivamente disponíveis** (coletados e inspecionados): uso do solo (estatísticas e piloto), rede pluvial, poços de visita, bocas de lobo, casas de bomba, recurso hídrico, risco CPRM e, via serviço, o MDT 2010.

**Integrados ao modelo:** **nenhum dos novos.** Estão coletados, auditados e versionados em `data/raw/` (com hash), mas ainda não processados nem exibidos na aplicação.

| Dado | Atributos suficientes para cálculo? |
|---|---|
| Uso do solo | **Parcialmente.** Dá a área de edificação e de via pavimentada, com faixa de coeficiente fundamentada (17,3% da área). O resto (75,1%) precisa de cenário declarado ou de dados de solo |
| MDT 2010 | **Parcialmente.** Resolução e cobertura servem, mas **licença, precisão vertical e aquisição em lote não estão confirmadas**; exatidão vertical de ~0,6 a 0,8 m |
| Rede pluvial | **Para inventário e grafo parcial**: diâmetro 100%, altitudes 88%. Sem identificador, sem nós e com material em 7,7%: **não dá capacidade** |
| Bocas de lobo | **Só localização.** Sem capacidade, sem relação com o trecho, profundidade zero em 82% |
| Casas de bomba | **Só nome e posição.** Capacidade vazia em 100% |
| Recurso hídrico | **Contexto** (natural e artificial separáveis), com divergência de 82% em relação aos arroios do projeto |
| CPRM | **Só contextualização** |

**Lacunas que impedem estimar volume retido:**
1. Coeficiente de escoamento sem fundamento em 83% da área (incluindo a classe mais comum nas áreas urbanas, "Jardins, Passeios ou Áreas semi urbanizadas").
2. Exatidão vertical do relevo maior que a profundidade das depressões de rua: só as depressões mais fundas (cerca de 1 m ou mais) são interpretáveis.
3. Capacidade de saída desconhecida: sem rugosidade (material em 7,7%), sem conexão confirmada entre boca e trecho, sem capacidade das bombas.

**Lacunas que impedem estimar duração:**
1. Nenhuma distribuição temporal da chuva (só uma série horária regional).
2. Nenhuma vazão de saída (bombas, condutos).
3. Nenhuma condição de contorno (nível do Guaíba).
4. Nenhum registro de alagamento com início e fim.

**Modelo mais avançado com segurança metodológica: o Nível 2 parcial, e apenas isso.**
- **Nível 1** (propensão topográfica à retenção) é viável agora, com o Copernicus, e com o MDT depois da confirmação de licença.
- **Nível 2** (contribuição e armazenamento potencial condicionados à chuva) é viável **com intervalos e cenários declarados**: a água gerada pelas superfícies impermeáveis (faixa fundamentada), as demais classes como cenário, e a água que **chega** a cada trecho. O armazenamento é **potencial topográfico**, não volume retido.
- **Nível 3** (estimativa hidráulica de acúmulo) **não é viável**: falta capacidade, conectividade confirmada, condições de contorno e validação.

Não iniciar modelagem hidráulica sem esses dados.

## 2. Os cinco fenômenos e o que cada um tem

| Fenômeno | O que existe | O que falta | Pode ser calculado? |
|---|---|---|---|
| **Água gerada** | Classes de uso; faixas de C para edificação e via pavimentada | C das demais classes; chuva efetiva (perdas e infiltração não representadas) | Sim, com intervalo; o resto por cenário |
| **Água transportada** | Relevo (30 m e 1 m); fluxo D8 já implementado | Direção real de escoamento em rua (meio-fio, sarjeta) | Sim, em escala de relevo (não de sarjeta) |
| **Água que chega à via** | Associação das áreas contribuintes aos trechos (fluxo acumulado) | Drenagem superficial por boca de lobo | Sim, como contribuição potencial |
| **Água potencialmente armazenada** | Depressões do MDT ou DEM | Relação cota-volume confiável; saída por drenagem | Só armazenamento potencial topográfico, com limite pela incerteza vertical |
| **Água removida por drenagem** | Rede, bocas, bombas (só geometria) | Capacidade, conexões, rugosidade, condições de contorno | **Não** |

Contribuição não é retenção: um trecho que recebe muita água pode escoá-la bem, e o fluxo acumulado não diz isso.

## 3. Proposta matemática (não implementada)

Estrutura: ΔS = V_entrada − V_saída. Com os dados atuais **só V_entrada e um limite superior de armazenamento são calculáveis; V_saída é desconhecido** e, portanto, ΔS **não** é calculado. O modelo reporta V_entrada e S_potencial, nunca ΔS.

- **Unidade espacial:** célula do relevo (a definir entre 1 m, com o MDT, e 30 m, com o Copernicus), agregada ao trecho de via por sua área contribuinte. A resolução é decisão pendente (item 5).
- **Cenário de chuva:** P em mm, parametrizado. Começar com 10, 30 e 60 mm **uniformes e hipotéticos**, mantendo a rastreabilidade com os experimentos anteriores; a arquitetura aceita depois campo espacial e série temporal. Uma chuva uniforme não diferencia ruas: só escala o volume (isso já foi medido).
- **Geração:** `V_ger(i) = P / 1000 × A_i × C_i` (m³), com P em mm, A em m² e C adimensional.
  - Para as classes com faixa fundamentada, C entra como **intervalo** `[C_min, C_max]` e o volume sai como intervalo.
  - Para as demais, C é um **cenário rotulado** (por exemplo baixo e alto), nunca um valor único apresentado como calibrado.
  - Áreas úmidas e corpos d'água ficam **fora** do cálculo de escoamento.
  - Não há chuva efetiva calculada (infiltração e perdas iniciais não representadas): V_ger é **água potencialmente escoada**, um limite superior.
- **Transporte:** fluxo D8 sobre o relevo com depressões preenchidas, **ponderado por V_ger** (não por contagem de células): `V_chega(t) = Σ V_ger das células a montante do trecho t`. Cada célula é contada uma vez (sem dupla contagem).
- **Armazenamento potencial:** `S_pot(j) = Σ (cota_preenchida − cota) × área_da_célula` por depressão j, apenas para depressões acima de um limiar de profundidade ligado à incerteza vertical do modelo. É capacidade topográfica, **não volume retido**: uma depressão só retém se não houver saída por drenagem, e a saída é desconhecida.
- **Saída por drenagem:** **não calculada**; classificada como **desconhecida**. O grafo da rede terá nós, trechos, pontos de captação, descargas e bombas, com cada conexão marcada como **confirmada, inferida ou desconhecida**. Conexão só por proximidade **não** é criada; coincidência de extremos entra como "inferida" e é contada separadamente. Diâmetro isolado não é capacidade.
- **Classificação:** classes relativas de propensão e a razão `V_chega / S_pot` (adimensional), sempre com o cenário, o intervalo e a classe de dado usada. Sem "profundidade", "tempo de inundação" nem "previsão de alagamento".

**Níveis apresentados separados e rotulados:** 1 (topográfico), 2 (condicionado à chuva, com intervalos) e 3 (hidráulico, não disponível). Nunca misturados em um único indicador sem explicação.

### Validação compatível com o nível

Coerência física (unidades, monotonicidade com P e com C); **conservação de massa** (a soma do que sai dos pontos terminais mais o armazenado é igual ao gerado); verificação de conectividade; **cenários sintéticos controlados** (bacia com saída conhecida), **rotulados como sintéticos e não como validação empírica**; sensibilidade ao cenário de C e ao relevo (MDT contra Copernicus); comparação qualitativa com ocorrências independentes quando houver (124 registros de 2013–2014, sem horário nem chuva; CPRM só como contexto). A validação espacial e temporal com métricas só entra com eventos datados.

## 4. Dados ainda necessários, por prioridade

1. **Licença, precisão vertical e entrega em lote do MDT 2010** (ou outro modelo de terreno de melhor resolução); existência de LiDAR.
2. **Eventos de alagamento com data, hora e local** (Defesa Civil, 156, ObservaPOA) e **chuva associada, com distribuição espacial e temporal**.
3. **Pedologia e declividade integradas**, para dar fundamento aos coeficientes de vegetação, campo, cultivo e solo exposto.
4. **Capacidade das casas de bomba** e dos condutos principais; identificadores e conexões da rede pluvial; legenda dos códigos das bocas de lobo.
5. **Condição de contorno:** nível do Guaíba.
6. **Composição da classe "Jardins, Passeios ou Áreas semi urbanizadas"** (fração permeável), a maior incerteza na cidade construída.

## 5. Decisões metodológicas

**Decididas** (25/11/2026):
1. **MDT municipal:** solicitação, aquisição e adoção adiadas. O Copernicus GLO-30 segue como referência; a resolução do processamento é a de 30 m, a mesma grade do DEM do projeto, sem reamostrar para resolução mais fina.
2. **Drenagem:** integrada como **inventário** geoespacial, sem presumir capacidade, operação nem conectividade hidráulica.
3. **Coeficientes:** dois métodos separados, **fundamentados** (só o que a referência sustenta) e **cenários determinísticos** com hipótese declarada.
4. **Abrangência:** toda Porto Alegre.

**Ainda pendentes**, agora com proposta em [fase3_entradas_e_saidas.md](fase3_entradas_e_saidas.md): a unidade de agregação da água que chega ao trecho; a apresentação do Método 2 para a classe "Jardins, Passeios ou Áreas semi urbanizadas"; e o tratamento do preenchimento de depressões (indicador relativo, não armazenamento). O limiar de profundidade de depressões deixou de ser decisão aberta: com o Copernicus (erro médio de 2,18 m) não há limiar defensável em metros, e o armazenamento em m³ não é produzido.

## 6. O que o produto pode afirmar hoje

- Pode dizer: exposição estimada (terreno e chuva regional); contexto da rede pluvial, dos pontos de captação, das casas de bomba e da hidrografia, **como inventário**; impermeabilização **estimada a partir do uso e ocupação do solo**, com a ressalva de que só 17,3% da área tem coeficiente fundamentado.
- **Não pode dizer:** previsão de alagamento, volume retido, profundidade, duração, capacidade de drenagem, que uma boca de lobo funciona ou descarrega em um trecho, que uma rua alaga em dado cenário.
