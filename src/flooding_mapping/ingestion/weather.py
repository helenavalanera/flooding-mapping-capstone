"""Daily rainfall per municipality from the Open-Meteo archive (ERA5-based reanalysis).

The free API is rate limited per minute, hour and day, and charges each request by
locations x days x variables (it reports the cost in ``X-RateLimit-Cost``). The download
is therefore split in chunks of (batch of municipalities, year), each cached on disk as
one JSON file, so an interrupted or rate-limited run resumes where it stopped and never
repeats a request. Years are fetched from the most recent to the oldest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..config import resolve

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "flooding-mapping-capstone (pesquisa academica)"
TIMEZONE = "America/Sao_Paulo"
BATCH = 20
CACHE_DIR = "data/raw/weather/archive"
OUTPUT = "data/interim/chuva_municipal.parquet"
ARCHIVE_LAG_DAYS = 6  # the reanalysis trails real time by about five days


class DailyLimit(RuntimeError):
    """The daily request quota is spent; resume tomorrow."""


def plan(ibges: list[str], start: date, end: date) -> list[dict]:
    """Chunks (batch of municipalities x calendar year), newest year first."""
    chunks = []
    for year in range(end.year, start.year - 1, -1):
        first, last = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
        for index in range(0, len(ibges), BATCH):
            chunks.append({"year": year, "batch": index // BATCH,
                           "ibge": ibges[index:index + BATCH], "start": first, "end": last})
    return chunks


def cache_path(root: Path, variable: str, chunk: dict) -> Path:
    return root / f"{variable}_{chunk['year']}_{chunk['batch']:02d}.json"


def request(params: dict, opener: Callable = urllib.request.urlopen):
    """GET the archive API; return (payload, headers) or raise HTTPError."""
    url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(params, safe=',')}"
    with opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as r:
        return json.loads(r.read()), dict(r.headers)


def wait_for(reason: str, sleep: Callable[[float], None]) -> None:
    """Sleep out a minute or hour limit; stop on the daily one."""
    text = reason.lower()
    if "daily" in text:
        raise DailyLimit(reason)
    seconds = 3700 if "hourly" in text else 65
    print(f"limite atingido ({reason[:60]}); aguardando {seconds}s", flush=True)
    sleep(seconds)


def fetch(towns: pd.DataFrame, chunk: dict, variable: str,
          opener: Callable = urllib.request.urlopen, sleep: Callable = time.sleep):
    """Download one chunk, waiting out minute/hour limits (at most 3 times)."""
    rows = towns.set_index("ibge").loc[chunk["ibge"]]
    params = {"latitude": ",".join(map(str, rows["lat"])),
              "longitude": ",".join(map(str, rows["lon"])),
              "start_date": chunk["start"].isoformat(), "end_date": chunk["end"].isoformat(),
              "daily": variable, "timezone": TIMEZONE}
    for attempt in range(4):
        try:
            return request(params, opener)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            wait_for(json.loads(exc.read() or b"{}").get("reason", "minutely"), sleep)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            # Network hiccup (for example a TLS handshake timeout): not a rate limit.
            if attempt == 3:
                raise
            print(f"falha de rede ({type(exc).__name__}); nova tentativa em {30 * (attempt + 1)}s", flush=True)
            sleep(30 * (attempt + 1))


def compact(payload, chunk: dict, variable: str) -> dict:
    """Keep only what the model needs: values, the grid cell used and its elevation."""
    items = payload if isinstance(payload, list) else [payload]
    return {
        "variable": variable, "start": chunk["start"].isoformat(), "end": chunk["end"].isoformat(),
        "ibge": chunk["ibge"],
        "grid": [[i["latitude"], i["longitude"]] for i in items],
        "elevation": [i.get("elevation") for i in items],
        "values": [i["daily"][variable] for i in items],
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def download(towns: pd.DataFrame, start: date, end: date, variable: str = "precipitation_sum",
             max_cost: float = 9000, root: Path | None = None,
             opener: Callable = urllib.request.urlopen, sleep: Callable = time.sleep) -> dict:
    """Fetch every missing chunk; stop before spending more than ``max_cost``."""
    root = root or resolve(CACHE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    chunks = plan(list(towns["ibge"]), start, end)
    spent, done, skipped = 0.0, 0, 0
    for chunk in chunks:
        path = cache_path(root, variable, chunk)
        if path.exists():
            skipped += 1
            continue
        try:
            payload, headers = fetch(towns, chunk, variable, opener, sleep)
        except DailyLimit as exc:
            print(f"limite diário: {exc}", flush=True)
            return {"baixados": done, "ja_em_cache": skipped, "custo": round(spent, 1),
                    "restantes": len(chunks) - done - skipped, "parou": "limite diário"}
        cost = float(headers.get("X-RateLimit-Cost", 0))
        path.write_text(json.dumps(compact(payload, chunk, variable), separators=(",", ":")))
        spent, done = spent + cost, done + 1
        print(f"{path.name}: custo {cost:.1f} (acumulado {spent:.0f})", flush=True)
        if spent + cost > max_cost:
            return {"baixados": done, "ja_em_cache": skipped, "custo": round(spent, 1),
                    "restantes": len(chunks) - done - skipped, "parou": "orçamento da execução"}
        sleep(1.0)
    return {"baixados": done, "ja_em_cache": skipped, "custo": round(spent, 1),
            "restantes": 0, "parou": "concluído"}


def load(variable: str = "precipitation_sum", root: Path | None = None) -> pd.DataFrame:
    """All cached chunks as one long table: ibge, data, <variable>, plus the grid cell."""
    root = root or resolve(CACHE_DIR)
    frames, cells = [], []
    for path in sorted(root.glob(f"{variable}_*.json")):
        chunk = json.loads(path.read_text())
        days = pd.date_range(chunk["start"], chunk["end"], freq="D")
        for ibge, values, grid, elev in zip(chunk["ibge"], chunk["values"], chunk["grid"],
                                            chunk["elevation"]):
            frames.append(pd.DataFrame({"ibge": ibge, "data": days, variable: values}))
            cells.append({"ibge": ibge, "grade_lat": grid[0], "grade_lon": grid[1],
                          "altitude_m": elev})
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["ibge", "data", variable])
    table[variable] = pd.to_numeric(table[variable], errors="coerce")
    table.attrs["grade"] = pd.DataFrame(cells).drop_duplicates("ibge")
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download municipal daily rainfall")
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default=None, help="default: today minus the reanalysis lag")
    parser.add_argument("--variable", default="precipitation_sum")
    parser.add_argument("--max-cost", type=float, default=9000,
                        help="stop after this much API cost (free daily limit is 10,000)")
    args = parser.parse_args(argv)
    towns = gpd.read_parquet(resolve("data/interim/municipios.parquet"))[["ibge", "lat", "lon"]]
    end = (date.fromisoformat(args.end) if args.end
           else date.today() - timedelta(days=ARCHIVE_LAG_DAYS))
    summary = download(towns, date.fromisoformat(args.start), end, args.variable, args.max_cost)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["parou"] == "concluído" else 3


if __name__ == "__main__":
    sys.exit(main())
