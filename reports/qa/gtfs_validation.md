# Validação do GTFS

- Arquivo: `/Users/helenaoliveirav/flooding-mapping/data/raw/gtfs_eptc.zip`
- Verificado em: 2026-10-24
- ZIP íntegro: sim
- Arquivos obrigatórios ausentes: nenhum

## Vigência declarada

- calendar_start: 2025-09-12
- calendar_end: 2025-12-12
- feed_start_date: 20250918
- feed_end_date: 20251218
- feed_version: 3.5@20250918

## Cobertura efetiva (calendar.txt + calendar_dates.txt)

- Primeiro dia com viagens: 2025-09-12
- Último dia com viagens: 2025-12-12
- Dias com serviço: 92
- Dias sem serviço dentro do intervalo: nenhum
- Mediana de viagens por dia da semana: friday=13085, monday=13085, saturday=7174, sunday=4502, thursday=13085, tuesday=13085, wednesday=13085
- Data de referência escolhida: 2025-10-30 (13085 viagens)

## Situação

- **Feed vencido** em relação à data da verificação. Usar apenas como referência histórica; não representa garantidamente o serviço atual.

## Problemas encontrados

- feed_end_date (2025-12-18) difere do último dia com viagens (2025-12-12)
- feed_start_date (2025-09-18) difere do primeiro dia com viagens (2025-09-12)

## Contagens

- calendar: 660
- calendar_dates: 3150
- trips: 29457
- stops: 5909
- routes: 395
- stop_times: 1761758
- feed_info: 1
- shapes: 223654
