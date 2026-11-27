# Avisos para o cidadão, áreas em exposição e o laço da comunidade

> **Frente arquivada (futuro monitoramento).** Os avisos aqui descritos não existem na versão atual; o estudo **não é serviço em tempo real**.

O Flooding Mapping é uma plataforma **para quem mora na cidade**, não um painel de gestão. A tela inicial do aplicativo (`/pwa/`, aba **Avisos**) responde: *o que a chuva pode afetar perto de mim, nas próximas horas, e como eu ajudo a confirmar?*

Tudo é **estimativa de um baseline sem validação em vias**. Não é alerta oficial; em emergência, a Defesa Civil é o 199. Nada abaixo prevê alagamento.

## O que existe

| Peça | O que faz | Onde |
|---|---|---|
| **Pontos de interesse (POIs)** | 1.720 locais do OpenStreetMap em Porto Alegre: hospitais, clínicas, farmácias, escolas, creches, faculdades, polícia, bombeiros, centros comunitários, mercados, terminais. A categoria diz *o que o lugar é*, nunca que está aberto ou serve de abrigo. | `pois.py`, `make pois` |
| **Bolsões de exposição** | Trechos em *atenção* ou *alto* na mesma hora, ampliados por um buffer (120 m) e fundidos em áreas, com km de via, escore e os POIs dentro. Prioridade = escore médio × (1 + ln(1 + soma dos pesos dos POIs)); os pesos são uma escolha editorial explícita. | `bolsoes.py`, `GET /api/bolsoes?h=` |
| **Avisos dos meus lugares** | Para até 5 lugares salvos no aparelho, a pior hora de exposição estimada nas próximas 12 h. As coordenadas vão sem nome e não são guardadas. | `Servico.avisos`, `POST /api/avisos` |
| **Apoio da comunidade (o laço)** | "Ainda está alagado" e "Já secou" sobre relatos. Dois apoios sobem a confiabilidade; dois "já secou" encerram a validade. Nunca confirmam nem interditam. | `Ocorrencias.apoiar`, `POST /api/ocorrencias/{id}/apoio` |
| **Aprendizado** | Os relatos **confirmados por operador ou apoiados por pessoas distintas** viram rótulos. Um modelo logístico sobre os cinco fatos de terreno é treinado e validado com blocos espaciais inteiros fora do treino. | `aprendizado.py`, `GET /api/aprendizado` |
| **Áreas sugeridas para verificar** | O 1% da malha com maior ranking (do modelo, ou da regra de terreno), agrupado em áreas, indicando se já há relato ativo. | `GET /api/areas-sugeridas` |

## O laço, passo a passo

1. Alguém **relata** uma rua alagada (entra como `reportada`, confiabilidade `baixa`).
2. Outras pessoas **apoiam** ("ainda está alagado") ou dizem que **secou**. Cada aparelho conta uma vez por ocorrência.
3. Com `apoios_minimos` (2) apoios, o relato sobe para `media` e passa a **contar como rótulo**: o risco da região sobe (piso de ocorrência) e o aprendizado o usa.
4. O aprendizado só treina com `min_ocorrencias` (8) e `min_positivos` (30 trechos). Ausência de relato **não é rótulo negativo** (aprendizado com positivos e não rotulados).
5. O modelo **só substitui a regra de terreno** se superar, em blocos espaciais, a PR-AUC da regra em `margem_ap` (10%). Caso contrário a regra segue valendo e `/api/aprendizado` diz o motivo, com as duas métricas.
6. As **áreas sugeridas** usam a fonte vigente (modelo ou regra) e mostram qual é.

Um operador (credencial) ainda pode confirmar com evidência e declarar interdição: só isso fecha uma rua no roteamento. O apoio da comunidade nunca fecha.

## Limites que precisam ser ditos

- Os rótulos herdam o **viés de quem reporta**: bairros com menos relatos aparecem menos. Sem verificação em campo, a sugestão é uma hipótese a verificar, não um achado.
- Na demonstração, os relatos e apoios são **sintéticos**; nela, o modelo **não superou a regra** (PR-AUC 0,003 contra 0,006), e a tela diz isso. Não houve rótulos reais para testar a adoção do modelo.
- A chuva é uma série regional (grade de ~10 km): o aviso de um lugar usa a chuva da cidade, não a do bairro.
- Os POIs são voluntários e podem estar desatualizados ou incompletos.
- Sem push: o app não envia notificação; a pessoa abre e consulta. Não há acompanhamento de posição.

## Como rodar

```
make pois      # uma vez: data/processed/pois_poa.parquet (a partir de data/interim/poa.osm.pbf)
make servir    # /pwa/ abre em Avisos
make demo      # mesma coisa com chuva e relatos sintéticos
```

Parâmetros: bloco `aprendizado` de `config/analysis.yaml` (todos provisórios). Sem `pois_poa.parquet` o serviço funciona sem a camada de pontos de interesse e diz isso.

## Território de Porto Alegre: bairros, drenagem e contexto social

Fonte: mapas públicos da Prefeitura de Porto Alegre ("Drenagem Pluvial" e "Áreas de Alagamento", exportados em KML) e, dentro deles, os aglomerados subnormais do IBGE 2010 (via ObservaPOA).

| O que entra | Como é usado |
|---|---|
| 94 bairros (polígonos unidos por nome) | cada trecho de rua é atribuído ao bairro que contém seu ponto médio; a tela **Exposição por bairro** mostra a parcela das ruas em Atenção ou Alto na hora escolhida |
| 679 trechos de arroio e 20 casas de bombas | camada de contexto no mapa; **não** entra no cálculo da exposição |
| Aglomerados subnormais (domicílios e pessoas por bairro) | contexto de quem mora na área, mostrado ao lado da exposição; **não** entra no cálculo e não aparece como polígono |

Preparar os dados: baixe `https://www.google.com/maps/d/kml?mid=1hKUlnRnx2aRiH3NBYnlLt4qXBUo&forcekml=1` e rode `python tools/preparar_territorio_poa.py <arquivo.kml>`. Gera `data/processed/territorio_poa.json` (fora do Git, ~240 KB; `FM_TERRITORIO` aponta outro caminho). Sem o arquivo, o app roda sem essas camadas e avisa.

API: `GET /api/territorio` (geometria, baixada uma vez) e `GET /api/bairros?h=` (parcela exposta por bairro e contexto).

Limites: a divisão por bairros é leitura da mesma estimativa, não uma estimativa nova; a chuva é uma série para a cidade inteira. O contexto social é de 2010 e não indica quem alaga, só quem vive onde a estimativa é alta.

Não foram usadas as ocorrências da Defesa Civil de 2013 que o mapa traz, porque têm nome e telefone de solicitantes. Os pontos e trechos de alagamento de 2013–14 só alimentam a conferência do terreno (`tools/validar_terreno_alagamentos_pmpa.py`, AUC 0,68 em 105 trechos) e a da altitude (`tools/validar_altitude_rrcm.py`, correlação de posto 0,99 e viés de +2,1 m).
