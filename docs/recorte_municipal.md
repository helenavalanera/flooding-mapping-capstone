# Recorte municipal dos resultados por trecho

Registro de 27/11/2026. **Problema encontrado na auditoria:** a malha de ruas do estudo (176.836 trechos do OpenStreetMap) vem de uma caixa em volta de Porto Alegre e inclui vias de cidades vizinhas. Pelo polígono do município (`data/processed/municipality.parquet`, 495,0 km²), **143.149 trechos estão dentro e 33.687 (19,0%) estão fora**. Fora do município não há uso do solo da Prefeitura, então esses trechos entravam como "sem dado" (2.910 dos 2.919) ou como zero (cerca de 30 mil em A e B), e puxavam para baixo a cobertura de drenagem (a faixa publicada de 43% sem rede cadastrada era de 29,7% dentro do município).

## O que mudou, e o que não mudou
- **Não mudou:** o motor, os parquets da Fase 3, as definições dos indicadores, os resultados por bairro (que já eram feitos só com trechos dentro dos bairros) e a validação com os registros.
- **Mudou:** o universo de apresentação. Um trecho é "de Porto Alegre" quando o **ponto médio** dele cai dentro do polígono do município. Tudo o que a landing mostra por trecho (mapas de manchas, legendas, números dos painéis e dos cartões) passa a valer só para esses 143.149 trechos. As vias de fora aparecem nos mapas em cinza bem claro, só como contexto, sem análise.
- **Critério novo, documentado:** o ponto médio é um critério simples e reprodutível; trechos que cruzam o limite municipal contam pelo ponto médio.

## Como reproduzir
`PYTHONPATH=src .venv/bin/python tools/gerar_recorte_municipal.py` recalcula, a partir dos mesmos parquets, os números por trecho dentro do município e escreve `static/data/recorte_municipal_poa.json`. O mesmo cálculo **sem** o recorte (campo `sem_recorte`) reproduz os valores já publicados em `reports/qa/fase3_execucao.json` (173.917 trechos com dado, mediana de contribuição de 32,1 m³, 134.941 sem preenchimento), o que valida o método (um teste confere). Os mapas são regenerados por `tools/gerar_mapa_manchas.py` e `tools/gerar_mapas_dimensoes.py`, que usam a mesma máscara (`Quadro.no_municipio`).

## Efeito nos números principais
| Número | Antes (malha inteira) | Depois (dentro do município) |
|---|---|---|
| Trechos | 176.836 | 143.149 |
| Trechos sem dado | 2.919 | 68 |
| Trechos com depressão (C) | 38.976 (22,0%) | 31.545 (22,0%) |
| Mediana e p99 da altura de preenchimento (C) | 0,59 m e 4,04 m | 0,63 m e 4,12 m |
| Mediana da contribuição (B, todos com dado) | 32,1 m³ | 49,8 m³ |
| Trechos com boca de lobo a até 50 m, quintil inferior de contribuição | 2,4% | 26,3% |
| Trechos com boca de lobo a até 50 m, quintil superior | 72,1% | 72,8% |

A afirmação anterior de que o quintil inferior quase não tem bocas de lobo (2%) era um efeito das vias de fora; dentro do município, a presença de bocas de lobo cresce de 26% no quintil inferior para 73% no superior.

## Resultados por bairro e painel de resultados
`src/flooding_mapping/resultados.py` (`carregar`) aplica o mesmo recorte: só trechos com ponto médio dentro do município entram em `resultados_poa.json`. Os indicadores sem relação com ruas (volumes por célula, cadastro de drenagem) não mudam. Muda a associação com os bairros em cinco deles, cujo polígono do mapa compartilhado passa um pouco do limite municipal (225 trechos no total, por exemplo Vila Assunção, de 771 para 649 trechos), e o achado D2 do painel, que agora diz 26% de trechos com boca de lobo a até 50 m no quintil inferior de contribuição e 73% no superior (antes 2% e 72%, efeito das vias de fora). Para refazer: `PYTHONPATH=src .venv/bin/python tools/gerar_resultados.py`, depois `tools/gerar_rankings.py`, `tools/gerar_mapas_dimensoes.py` e `tools/gerar_landing.py`.

## Tiles de escoamento (regenerados com o recorte)
Gerados em 27/11/2026 por `PYTHONPATH=src .venv/bin/python tools/preparar_camada_fase3.py` (o recorte é o padrão; `--sem-recorte` reproduz a versão anterior). Tiles, fragmentos de detalhe, classes visuais e `meta.json` saem da mesma tabela filtrada, então o número `n` de cada trecho vale nos dois. O `meta.json` registra `recorte_municipal` (33.687 trechos de fora excluídos de 176.836). Nenhum parquet da Fase 3 foi alterado.

| | Antes (malha inteira) | Depois (dentro do município) |
|---|---|---|
| Trechos nos tiles e nos fragmentos | 176.836 | 143.149 (143.081 com dado, 68 sem dado) |
| Tiles .pbf z13, z14, z15 | 99, 357 e 1.428 | 80, 252 e 910 |
| Tamanho dos tiles (sem compressão) | 33,3 MB | 27,1 MB (menos 18%) |
| Fragmentos de detalhe | 36,4 MB | 30,6 MB |
| Maior tile (z13) | 798 KB | 798 KB (o centro, que é de dentro) |
| Extensão dos tiles z13 (oeste a leste, sul a norte) | -51,372 a -50,977 e -30,297 a -29,879 | -51,328 a -50,977 e -30,297 a -29,917 |

As classes visuais seguem o mesmo critério (quantis dos trechos analisados) e mudaram só nos decimais dos cortes das classes de contribuição, por usarem agora o universo municipal (por exemplo, o corte da classe mais alta de contribuição do Método 1, limite superior, foi de 214.725 para 212.343 m²); os cortes de cobertura, de posto topográfico e a lista de quantis são idênticos. Validação: 35 testes de integridade contra os parquets passam (identificadores únicos e na ordem, valores iguais aos parquets, ausência continua ausência, os três pacotes não se misturam, conversão de unidade para as três chuvas e todos os trechos, menos os de poucos decímetros, presentes no zoom máximo).
