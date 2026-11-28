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
RAIZ = Path(__file__).resolve().parents[3]
PUBLICACAO = RAIZ / "config/publicacao.json"   # produção: onde estão os dados derivados no R2 (r2_url nulo = build local, sem R2)
ASSETS = ("index.html", "painel.js", "territorio.js", "fase3-dados.js", "fase3.js", "drenagem.js", "geoai.js", "resultados.js", "simulador.js", "mapa.js", "mapa2d.js", "mapa-base.js", "carregar-mapa.js", "modo-mapa.js", "logic.js", "style.css", "config-dados.js", "icone-192.png", "icone-512.png", "favicon-32.png", "marca-logo.png")
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
URL_R2_LOCAL = re.compile(r"^http://(127\.0\.0\.1|localhost):\d{1,5}$")   # só para simular o bucket no computador (testes); nunca vale em produção
ORIGEM_R2 = re.compile(r"^https://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?$")


def com_origem_do_r2(csp: str, origem: str | None) -> str:
    """Acrescenta a origem pública do R2 (tiles, fragmentos e PMTiles lidos por faixas de bytes) a ``connect-src`` e a ``img-src``. Só origem https, sem caminho."""
    if not origem:
        return csp
    if not (ORIGEM_R2.match(origem) or URL_R2_LOCAL.match(origem)):   # a segunda forma só existe para simular o bucket no computador (testes)
        raise SystemExit(f"--r2-origem deve ser uma origem https sem caminho (por exemplo https://dados.exemplo.org), e não {origem!r}")
    return csp.replace("img-src 'self' data: blob:", f"img-src 'self' data: blob: {origem}").replace("connect-src 'self'", f"connect-src 'self' {origem}")


# ------------------------------------------------------------------------------------------------------------------------------ configuração de produção
URL_R2 = re.compile(r"^https://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?(/[A-Za-z0-9._~-]+)*$")
VERSAO = re.compile(r"^d-[0-9a-f]{12}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
CONFIG_LOCAL = ('  fase3: "fase3/", drenagem: "drenagem/", geoai: "geoai/", versao: null, meta_sha256: { fase3: null, drenagem: null, geoai: null },', '  mapa: "/mapa/rs.pmtiles",')


def carregar_publicacao(caminho: Path = PUBLICACAO, local: bool = False) -> dict | None:
    """A configuração de produção, validada, ou ``None`` quando ``r2_url`` é nulo (build local). Os hashes de integridade vêm do resumo versionado do manifesto
    (docs/manifestos/), nunca digitados aqui; versão, hashes e URL malformados interrompem o build em vez de publicar uma configuração que não confere."""
    pub = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not pub.get("r2_url"):
        return None
    url = pub["r2_url"]
    if not (URL_R2.match(url) or (local and URL_R2_LOCAL.match(url))) or url.endswith("/"):
        raise SystemExit(f"r2_url deve ser https://host[/caminho], sem barra no fim: {url!r}")
    if not VERSAO.match(pub["versao"]):
        raise SystemExit(f"versão dos dados malformada: {pub['versao']!r}")
    man = json.loads((RAIZ / pub["manifesto"]).read_text(encoding="utf-8"))
    if man["versao_dos_dados"] != pub["versao"]:
        raise SystemExit(f"o manifesto {pub['manifesto']} é da versão {man['versao_dos_dados']}, e a configuração pede {pub['versao']}")
    hashes = {c: man["camadas"][c]["meta_sha256"] for c in pub["camadas_publicadas"]}
    if not all(HASH.match(h) for h in hashes.values()) or set(hashes) < {"fase3", "drenagem"}:
        raise SystemExit("hashes de integridade ausentes ou malformados no manifesto")
    geoai = None
    if pub.get("geoai_publicada"):   # camada E (experimental): prefixo PRÓPRIO no bucket, manifesto próprio, sem tocar a versão principal
        g = pub.get("geoai") or {}
        if not re.fullmatch(r"geoai-[0-9a-f]{12}", g.get("prefixo", "")):
            raise SystemExit("geoai_publicada exige geoai.prefixo no formato geoai-<12 hex> em config/publicacao.json")
        gman = json.loads((RAIZ / g["manifesto"]).read_text(encoding="utf-8"))
        if gman["versao_dos_dados"] != g["prefixo"] or not HASH.match(gman["geoai"]["meta_sha256"]):
            raise SystemExit("o manifesto da camada E não corresponde ao prefixo ou não traz o hash do meta.json")
        geoai = {"url": f"{url}/{g['prefixo']}/geoai/", "meta_sha256": gman["geoai"]["meta_sha256"]}
    return {**pub, "hashes": hashes, "manifesto_dados": man, "geoai_cfg": geoai}


def origem_do_r2(pub: dict) -> str:
    return re.match(r"^(https?://[^/]+)", pub["r2_url"]).group(1)


def config_de_producao(texto: str, pub: dict) -> str:
    """``config-dados.js`` de produção: URLs do R2 da versão, hashes esperados dos meta.json (a página recusa dados que não conferem) e a camada E só se estiver publicada."""
    base = f"{pub['r2_url']}/{pub['versao']}"
    h = pub["hashes"]
    geoai = pub.get("geoai_cfg")
    novo = (f'  fase3: "{base}/fase3/", drenagem: "{base}/drenagem/", geoai: {json.dumps(geoai["url"]) if geoai else "null"}, versao: "{pub["versao"]}", '
            f'meta_sha256: {{ fase3: "{h["fase3"]}", drenagem: "{h["drenagem"]}", geoai: {json.dumps(geoai["meta_sha256"]) if geoai else "null"} }},')
    for antigo in CONFIG_LOCAL:
        if antigo not in texto:
            raise SystemExit(f"config-dados.js mudou e o build não achou: {antigo[:50]}")
    return texto.replace(CONFIG_LOCAL[0], novo, 1).replace(CONFIG_LOCAL[1], f'  mapa: "{base}/{pub["mapa_arquivo"]}",', 1)


def cabecalhos(r2_origem: str | None = None) -> str:
    """Conteúdo do ``_headers`` do Pages. Regras que casam com a mesma página SOMAM cabeçalhos, por isso as páginas enquadráveis soltam a política geral (``!``) antes de pôr a sua."""
    geral, enquadravel = com_origem_do_r2(CSP, r2_origem), com_origem_do_r2(CSP_ENQUADRAVEL, r2_origem)
    seguranca = ["X-Content-Type-Options: nosniff", "Referrer-Policy: strict-origin-when-cross-origin", "Permissions-Policy: geolocation=(), camera=(), microphone=()"]
    linhas = ["/*", f"  Content-Security-Policy: {geral}", *(f"  {h}" for h in seguranca)]
    for rota in ("/", "/index.html", "/painel.html"):
        linhas += [rota, "  ! Content-Security-Policy", f"  Content-Security-Policy: {enquadravel}"]
    # Cache do navegador e do CDN. HTML, JS e CSS ficam com a revalidação padrão do Pages (ETag): uma publicação nova vale na hora. O que muda pouco e pesa fica em cache.
    linhas += ["/vendor/*", "  Cache-Control: public, max-age=86400",                                        # bibliotecas e glifos do mapa
               "/inicio/img/*", "  Cache-Control: public, max-age=3600, stale-while-revalidate=86400",      # os quatro mapas WebP e os gráficos da landing (não têm hash no nome)
               "/data/*", "  Cache-Control: public, max-age=3600, stale-while-revalidate=86400",            # resultados, rankings e números dos mapas
               "/icone-*", "  Cache-Control: public, max-age=86400"]
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


def build_site(out: Path, fase3: Path | None = None, drenagem: Path | None = None, r2_origem: str | None = None, publicacao: dict | None = None) -> dict:
    """Escreve o site em ``out`` e devolve o que foi publicado. ``publicacao`` (de ``carregar_publicacao``) liga a configuração de produção: URLs e hashes do R2 no
    ``config-dados.js`` e a origem do R2 na política de conteúdo; sem ela o site fica com a configuração local."""
    shutil.rmtree(out, ignore_errors=True)
    copiar_interface(out)
    if publicacao:
        (out / "config-dados.js").write_text(config_de_producao((out / "config-dados.js").read_text(encoding="utf-8"), publicacao), encoding="utf-8")
        r2_origem = r2_origem or origem_do_r2(publicacao)
    published = {"territorio": "poa"}
    if publicacao:
        published["producao"] = {"versao": publicacao["versao"], "r2_url": publicacao["r2_url"], "geoai": bool(publicacao.get("geoai_publicada")), "geoai_prefixo": (publicacao.get("geoai") or {}).get("prefixo") if publicacao.get("geoai_publicada") else None}
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
    parser.add_argument("--publicacao", type=Path, default=PUBLICACAO, help="config/publicacao.json: R2 e versão de produção (r2_url nulo = build local)")
    parser.add_argument("--sem-publicacao", action="store_true", help="ignora config/publicacao.json e gera a configuração local")
    args = parser.parse_args()
    pub = None if args.sem_publicacao else carregar_publicacao(args.publicacao)
    print(json.dumps(build_site(args.out, args.fase3, args.drenagem, args.r2_origem, pub), ensure_ascii=False))


if __name__ == "__main__":
    main()
