"""Monta o site estático de Porto Alegre: a landing, o painel de análise (resultados, mapa, simulador e proveniência) e, opcionalmente, as camadas derivadas.

Tudo o que é publicado é arquivo estático: a página só lê JSON. Não há modelo, previsão, consulta de rede nem credencial na montagem. As camadas derivadas
(``fase3/`` e ``drenagem/``) vêm de dados que não vão ao Git e só entram com ``--fase3`` e ``--drenagem``; o mapa-base (.pmtiles) é publicado à parte.

A montagem do site de duas escalas (Rio Grande do Sul e Porto Alegre), com previsão de 72 h e bloqueios de rodovias, está arquivada em
``app/arquivo/site_estadual.py`` e não é carregada aqui.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

STATIC = Path(__file__).parent / "static"
ASSETS = ("index.html", "painel.js", "territorio.js", "fase3-dados.js", "fase3.js", "drenagem.js", "resultados.js", "simulador.js", "mapa.js", "mapa2d.js", "mapa-base.js", "logic.js", "style.css", "config-dados.js", "icone-192.png", "icone-512.png")
ENTRADA = Path(__file__).parent / "entrada"   # raiz da versão estática: leva à landing (ou ao painel, quando o endereço pede)
# O PWA de rotas, o painel estadual e a aplicação instalável estão arquivados em app/arquivo/ e não entram no site.

# ---------------------------------------------------------------------------------------------------------------------------------------- cabeçalhos
# O Cloudflare Pages não tem o servidor Python que aplica a política de conteúdo em desenvolvimento: ela vai no arquivo ``_headers`` da raiz do site.
# A política é a mesma de ``flooding_mapping.servidor.CSP`` (um teste confere), acrescida da origem pública do R2 quando há uma. Este módulo não importa o servidor.
CSP = ("default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
       "img-src 'self' data: blob: https://cdnjs.cloudflare.com https://s3.amazonaws.com; "
       "connect-src 'self' https://s3.amazonaws.com; worker-src 'self' blob:; child-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'")
# A página "No celular" mostra a interface real num quadro da MESMA origem: a raiz (que leva ao painel) e o painel podem ser enquadrados por 'self'; o resto, por ninguém.
CSP_ENQUADRAVEL = CSP.replace("frame-ancestors 'none'", "frame-ancestors 'self'")
ORIGEM_R2 = re.compile(r"^https://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?$")


def com_origem_do_r2(csp: str, origem: str | None) -> str:
    """Acrescenta a origem pública do R2 (tiles, fragmentos e PMTiles lidos por faixas de bytes) a ``connect-src`` e a ``img-src``. Só origem https, sem caminho."""
    if not origem:
        return csp
    if not ORIGEM_R2.match(origem):
        raise SystemExit(f"--r2-origem deve ser uma origem https sem caminho (por exemplo https://dados.exemplo.org), e não {origem!r}")
    return csp.replace("img-src 'self' data: blob:", f"img-src 'self' data: blob: {origem}").replace("connect-src 'self'", f"connect-src 'self' {origem}")


def cabecalhos(r2_origem: str | None = None) -> str:
    """Conteúdo do ``_headers`` do Pages. Regras que casam com a mesma página SOMAM cabeçalhos, por isso as páginas enquadráveis soltam a política geral (``!``) antes de pôr a sua."""
    geral, enquadravel = com_origem_do_r2(CSP, r2_origem), com_origem_do_r2(CSP_ENQUADRAVEL, r2_origem)
    seguranca = ["X-Content-Type-Options: nosniff", "Referrer-Policy: strict-origin-when-cross-origin", "Permissions-Policy: geolocation=(), camera=(), microphone=()"]
    linhas = ["/*", f"  Content-Security-Policy: {geral}", *(f"  {h}" for h in seguranca)]
    for rota in ("/", "/index.html", "/painel.html"):
        linhas += [rota, "  ! Content-Security-Policy", f"  Content-Security-Policy: {enquadravel}"]
    linhas += ["/vendor/*", "  Cache-Control: public, max-age=86400"]      # bibliotecas e glifos do mapa: mudam raramente
    return "\n".join(linhas) + "\n"


def copiar_interface(out: Path) -> None:
    """A interface estática, sem nada que dependa de rede, de modelo ou de dado derivado: o que vai para o Pages.

    A raiz (``index.html``) é a porta de entrada, que leva à landing; o painel é ``painel.html``. Os dados derivados (fase3/, drenagem/) e o mapa-base
    ficam de fora: são publicados à parte (R2) ou acrescentados por ``build_site``.
    """
    (out / "data").mkdir(parents=True)
    for name in ASSETS:
        shutil.copy(STATIC / name, out / name)
    (out / "index.html").rename(out / "painel.html")   # o painel passa a ser painel.html; a raiz leva à landing
    shutil.copy(ENTRADA / "index.html", out / "index.html")
    shutil.copy(ENTRADA / "entrada.js", out / "entrada.js")
    shutil.copytree(STATIC / "inicio", out / "inicio")   # landing: os links para o painel são relativos, então funciona sob o caminho de um repositório no Pages
    shutil.copytree(STATIC / "vendor", out / "vendor")   # bibliotecas e estilos do mapa-base e fontes dos rótulos (o .pmtiles é servido à parte)
    for path in (STATIC / "data").glob("*"):
        shutil.copy(path, out / "data" / path.name)


def build_site(out: Path, fase3: Path | None = None, drenagem: Path | None = None, r2_origem: str | None = None) -> dict:
    """Escreve o site em ``out`` e devolve o que foi publicado."""
    shutil.rmtree(out, ignore_errors=True)
    copiar_interface(out)
    published = {"territorio": "poa"}
    if fase3 is not None:   # opt-in (--fase3): tiles e detalhe da camada da Fase 3, dado derivado que nunca vai ao Git
        shutil.copytree(fase3, out / "fase3")
        published["fase3"] = True
    if drenagem is not None:   # opt-in (--drenagem): a camada de drenagem cadastrada, também derivada e fora do Git
        shutil.copytree(drenagem, out / "drenagem")
        published["drenagem"] = True
    (out / ".nojekyll").write_text("")
    (out / "_headers").write_text(cabecalhos(r2_origem), encoding="utf-8")
    published["cabecalhos"] = True
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description="Monta o site estático de Porto Alegre")
    parser.add_argument("--out", type=Path, default=Path("site"))
    parser.add_argument("--drenagem", type=Path, default=None, help="data/processed/drenagem_web (tools/preparar_camada_drenagem.py): publica a camada de drenagem cadastrada com o site")
    parser.add_argument("--fase3", type=Path, default=None, help="data/processed/fase3_web (tools/preparar_camada_fase3.py): publica a camada da Fase 3 com o site")
    parser.add_argument("--r2-origem", default=None, help="origem pública do R2 (https://dados.exemplo.org), acrescentada a connect-src e img-src do _headers")
    args = parser.parse_args()
    print(json.dumps(build_site(args.out, args.fase3, args.drenagem, args.r2_origem), ensure_ascii=False))


if __name__ == "__main__":
    main()
