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
from flooding_mapping.demonstracao import aplicar, criar_servico_demo  # noqa: E402
from flooding_mapping.linguagem.explicar import Explicador  # noqa: E402


def montar_demo(estaticos: Path | None = None, seletor: bool = False, arquivo: Path | None = None):
    """The demonstration server. With ``seletor`` it is a "real" service whose rain is a flat dry series (so no network is needed) next to the
    isolated demonstration service, to test the page's switch; without it, the whole server is the demonstration."""
    srv.LIMITE_LEITURA_POR_MIN = 10**6   # the tests switch tabs far faster than a person; the real limit stays in servidor.py
    servico, _ = srv.montar(env={})
    if not os.environ.get("DEMO_GEMINI"):   # the browser tests never spend the language provider's quota
        servico.explicador = Explicador(None)
    demo = None
    if seletor:
        agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).floor("h")
        indice = pd.date_range(agora - pd.Timedelta(days=5), agora + pd.Timedelta(days=3, hours=-1), freq="h")
        seca = (pd.Series(0.0, index=indice), {"fonte": "https://api.open-meteo.com/v1/forecast (série seca de teste)", "emitido_em_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")})
        servico.chuva = ChuvaHoraria(0, 0, fonte=lambda lat, lon: seca)
        servico.store, servico.token_operador = oc.Ocorrencias(), "token-do-servico-real-com-mais-de-24-caracteres"
        demo = criar_servico_demo(servico)
    else:
        aplicar(servico)
    if estaticos:
        srv.RAIZES = (estaticos, srv.RAIZES[1])
    if arquivo:   # o PWA arquivado (app/arquivo/) só é servido por opt-in: os testes do app de rotas o ligam; os da aplicação atual, não
        srv.RAIZES = tuple(srv.RAIZES) + (arquivo,)
    return servico, demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--porta", type=int, default=8766)
    parser.add_argument("--estaticos", type=Path, default=None)
    parser.add_argument("--avisar", action="store_true", help="mostra os endereços e a credencial de demonstração")
    parser.add_argument("--arquivo-pwa", action="store_true", help="serve também o PWA arquivado (app/arquivo/) em /pwa/")
    parser.add_argument("--arquivo", type=Path, default=None, help="serve o PWA arquivado a partir desta pasta (uma cópia, para testes que a alteram)")
    parser.add_argument("--seletor", action="store_true", help="serviço real (chuva seca de teste) com o modo de demonstração isolado ao lado")
    args = parser.parse_args()
    servico, demo = montar_demo(args.estaticos, args.seletor, args.arquivo or (srv.ARQUIVO if args.arquivo_pwa else None))
    print("pronto", flush=True)
    if args.avisar:
        print(f"""
DEMONSTRAÇÃO COM DADOS SINTÉTICOS (chuva inventada, ocorrências de demonstração; tudo em memória, some ao parar)
  painel (desktop): http://127.0.0.1:{args.porta}/
  PWA arquivado:     http://127.0.0.1:{args.porta}/pwa/   (só com --arquivo-pwa)
  credencial do operador (só desta demonstração): {servico.token_operador}
  para limpar e recomeçar: pare (Ctrl+C) e rode de novo""", flush=True)
    ThreadingHTTPServer((os.environ.get("DEMO_HOST", "127.0.0.1"), args.porta), srv.criar_handler(servico, "", servico_demo=demo)).serve_forever()
