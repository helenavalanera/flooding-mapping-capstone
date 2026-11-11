"""Server for the browser tests only: the REAL street network of Porto Alegre with a SYNTHETIC storm.

The live forecast is often dry, which would leave the risk screens empty. Here the rain series is made up
(and says so in its source), one occurrence is reported and one closure is confirmed, all in memory. Nothing
of this is data about the world, and nothing is written to disk.

    python tests/e2e/servidor_demo.py --porta 8766 [--estaticos PASTA] [--avisar]    (ou: make demo)
"""

import argparse
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from flooding_mapping import ocorrencias as oc  # noqa: E402
from flooding_mapping import servidor as srv  # noqa: E402
from flooding_mapping.chuva_horaria import ChuvaHoraria  # noqa: E402
from flooding_mapping.linguagem.explicar import Explicador  # noqa: E402


def montar_demo(estaticos: Path | None = None):
    srv.LIMITE_LEITURA_POR_MIN = 10**6   # the tests switch tabs far faster than a person; the real limit stays in servidor.py
    servico, _ = srv.montar(env={})
    agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).floor("h")
    indice = pd.date_range(agora - pd.Timedelta(days=5), agora + pd.Timedelta(days=3, hours=-1), freq="h")
    serie = pd.Series(0.0, index=indice)
    serie[agora + pd.Timedelta(hours=3): agora + pd.Timedelta(hours=7)] = 14.0
    serie[agora + pd.Timedelta(hours=8): agora + pd.Timedelta(hours=10)] = 4.0
    meta = {"fonte": "SÉRIE SINTÉTICA DE DEMONSTRAÇÃO (não é previsão)", "emitido_em_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "primeira_hora": str(indice[0]), "ultima_hora": str(indice[-1]), "resolucao_espacial": "demonstração"}
    servico.chuva = ChuvaHoraria(0, 0, fonte=lambda lat, lon: (serie, meta))
    servico.store, servico.token_operador = oc.Ocorrencias(), "demo-operador-com-mais-de-24-caracteres"
    if not os.environ.get("DEMO_GEMINI"):   # the browser tests never spend the language provider's quota
        servico.explicador = Explicador(None)
    r = servico.rede
    candidatas = [i for i in r.proximos(-51.2300, -30.0300, 600) if r.arestas["drive"].iat[i] and r.arestas["nome"].iat[i]]
    for i, situacao in ((candidatas[0], "reportada"), (candidatas[len(candidatas) // 2], "confirmada")):
        rec = servico.store.relato({"lon": float(r.no_lon[r.u[i]]), "lat": float(r.no_lat[r.u[i]]), "tipo": "alagamento_via", "severidade": "alta",
                                    "impacto_circulacao": "interdicao", "segmento_ids": [str(r.ids[i])], "descricao": "demonstração"})
        if situacao == "confirmada":
            servico.store.mudar_situacao(rec["id"], "confirmada", por="demo", evidencia="Ocorrência de demonstração, não é real")
    if estaticos:
        srv.RAIZES = (estaticos, srv.RAIZES[1])
    return servico


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--porta", type=int, default=8766)
    parser.add_argument("--estaticos", type=Path, default=None)
    parser.add_argument("--avisar", action="store_true", help="mostra os endereços e a credencial de demonstração")
    args = parser.parse_args()
    servico = montar_demo(args.estaticos)
    print("pronto", flush=True)
    if args.avisar:
        print(f"""
DEMONSTRAÇÃO COM DADOS SINTÉTICOS (chuva inventada, ocorrências de demonstração; tudo em memória, some ao parar)
  painel (desktop): http://127.0.0.1:{args.porta}/
  PWA (celular):     http://127.0.0.1:{args.porta}/pwa/
  credencial do operador (só desta demonstração): {servico.token_operador}
  para limpar e recomeçar: pare (Ctrl+C) e rode de novo""", flush=True)
    ThreadingHTTPServer((os.environ.get("DEMO_HOST", "127.0.0.1"), args.porta), srv.criar_handler(servico, "")).serve_forever()
