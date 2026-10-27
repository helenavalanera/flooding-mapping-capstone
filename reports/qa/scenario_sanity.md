# Teste de sanidade do bloqueio de segmentos

Cenário: `S-E20250618-04-100-all` (Dona Teodora × A. J. Renner, raio 100 m, todas as redes).
Status dos trechos: **candidato** (não validado por revisão humana).

- PBF derivado: `data/interim/scenarios/S-E20250618-04-100-all.osm.pbf` (original intacto)
- 52 segmentos bloqueados; 30 vias divididas
- Pares de pontos a ~400 m de cada lado do cruzamento; partida 2025-10-30 07:00; r5py 1.1.7

| Par | A pé, base (min) | A pé, bloqueado | Carro, base | Carro, bloqueado |
|---|---|---|---|---|
| NO → SE | 18 | 34 | 2 | 6 |
| NO → S | 15 | 21 | 2 | 4 |
| N → SE | 17 | 25 | 2 | 4 |
| N → S | 15 | 29 | 2 | 5 |

Todos os tempos aumentaram: o bloqueio altera efetivamente as rotas que dependem dos trechos.

Observação: a unidade de bloqueio é o segmento entre dois nós OSM consecutivos que intersecta
a zona; segmentos longos podem se estender além do raio.
