# Robustez — notas de interpretação

Execução: 19 cenários × 2 redes, 500 pares por medida, semente 20261025
(`reports/qa/robustness_run.json`; tabela completa em `outputs/tables/robustness.csv`).

- Rede de pedestres: grafo não direcionado (150.729 nós). Rede viária: grafo direcionado com
  `oneway` (119.403 nós). A maior componente da linha de base reúne 95,3% e 97,9% dos nós.
- A eficiência **global** quase não muda com bloqueios pontuais: R_E ≥ 0,996 em todos os
  cenários isolados; o menor valor é o dos bloqueios simultâneos de 18/06/2025 com 150 m
  (0,987 na viária, 0,995 na de pedestres).
- A eficiência **local** usa pares sorteados entre nós a até 1 km da zona bloqueada. Como a
  zona cresce com o raio, o conjunto de pares muda: **R_E local não é comparável entre raios**,
  só entre redes ou entre cenários de mesmo raio.
- Piloto Dona Teodora × A. J. Renner (100 m): R_E local 0,834 (pedestres) e 0,920 (viária);
  valores idênticos aos da execução isolada anterior (mesma semente).
- A maior componente conexa não mede acessibilidade nem resiliência por si só.
