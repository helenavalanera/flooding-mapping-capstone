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
