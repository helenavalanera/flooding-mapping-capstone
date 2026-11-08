# MobilityData GTFS Validator — resumo

- Validador: `gtfs-validator-8.0.1-cli.jar` (SHA-256 `19293ddd9b6f954f216d4f12054bd8a3232921751c4484339e339764a91000e2`)
- Java: OpenJDK 21.0.13 (Homebrew)
- Feed: `data/raw/gtfs_eptc.zip` (SHA-256 `7ad9c99183e7a867cacdd3fa0e6f813125cf0c5b772c2188bea03f4fa6a5d76f`)
- Executado em: 2026-10-24T23:21:15-03:00, com `-d 2025-10-30` (data de referência)
- Relatório completo (não versionado): `data/interim/gtfs_validator_output/report.html`

Comando:

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@21 $JAVA_HOME/bin/java -jar \
  data/interim/tools/gtfs-validator-8.0.1-cli.jar \
  -i data/raw/gtfs_eptc.zip -o data/interim/gtfs_validator_output -d 2025-10-30
```

Janela declarada (`feed_info`): 2025-09-18 a 2025-12-18.
Janela de serviço calculada pelo validador: 2025-09-12 a 2025-12-12.

| Severidade | Código | Ocorrências |
|---|---|---|
| ERROR | — | 0 |
| WARNING | stop_too_far_from_shape | 2032 |
| WARNING | fast_travel_between_consecutive_stops | 1528 |
| WARNING | fast_travel_between_far_stops | 1419 |
| WARNING | unusable_trip | 1243 |
| WARNING | unused_trip | 1243 |
| WARNING | stop_without_stop_time | 668 |
| WARNING | unused_shape | 214 |
| WARNING | route_color_contrast | 119 |
| WARNING | stops_match_shape_out_of_order | 58 |
| INFO | service_window_outside_feed_period | 611 |
| — | system_errors | 0 |

Implicações para a análise:

- Sem erros bloqueantes; o feed é processável.
- `unusable_trip`/`unused_trip` (1243): viagens com menos de duas paradas ou sem
  serviço; o roteador as ignora, mas reduzem a oferta efetiva representada.
- `stop_too_far_from_shape` e `stops_match_shape_out_of_order`: afetam a
  reconstrução de itinerários a partir de `shapes.txt` (cenário de limite superior).
- Feed vencido desde 2025-12-12: usado como referência histórica.
