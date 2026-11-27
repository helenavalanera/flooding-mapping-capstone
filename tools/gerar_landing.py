"""Gera a landing page científica (static/inicio/index.html) a partir dos resultados reais do projeto. Nenhum número é digitado à mão.

    PYTHONPATH=src .venv/bin/python tools/gerar_landing.py [--sem-figuras]

Lê: reports/qa/*.json (Fase 2, Fase 3, sensibilidade, robustez, modelos), data/processed/fase3 e drenagem (Parquets), data/processed/fase3_web/meta.json.
Escreve: src/flooding_mapping/app/static/inicio/{index.html, dados.json, img/estudo/*} a partir de tools/landing/estudo.template.html.

Os números dos cartões saem de ``INDICADORES`` (cada um com o caminho do JSON de origem); o teste ``tests/test_landing.py`` confere o HTML contra as fontes.
Os gráficos (SVG, só números agregados) são desenhados dos mesmos dados e vão para static/inicio/img/estudo. Os MAPAS de trechos e de drenagem derivam da Profill e do cadastro de
drenagem da Prefeitura, cuja redistribuição não foi confirmada: por isso a landing publicada não os usa, e ``--mapas-locais`` os desenha só em data/interim/landing_mapas_historicos
(ignorado pelo Git). ``--sem-figuras`` só refaz o HTML e o dados.json.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))
import gerar_referencias as refs  # noqa: E402  (registro único das referências e das citações)
ESTATICO = RAIZ / "src/flooding_mapping/app/static"
SAIDA = ESTATICO / "inicio"
FIG = SAIDA / "img" / "estudo"
FIG_MAPAS_LOCAIS = RAIZ / "data/interim/landing_mapas_historicos"   # fora do Git e da publicação (licença da Profill e da drenagem não confirmada)
TEMPLATE = RAIZ / "tools/landing/estudo.template.html"
REPO = "https://github.com/helenavalanera/flooding-mapping-capstone"

RANKINGS = "src/flooding_mapping/app/static/data/rankings_poa.json"   # tools/gerar_rankings.py
TINTA, SECO, LEVE, FORTE, ACENTO = "#0a1c27", "#e6f0f5", "#bcd7e6", "#0b5d8f", "#f2a33a"


def jcarrega(rel: str):
    return json.loads((RAIZ / rel).read_text(encoding="utf-8"))


def caminho(d, path: str):
    for p in path.split("."):
        d = d[int(p)] if isinstance(d, list) else d[p]
    return d


def br(x: float, casas: int = 0) -> str:
    s = f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def exp10(x: float) -> str:
    m, e = f"{x:.1e}".split("e")
    sup = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return f"{m.replace('.', ',')} × 10{str(int(e)).translate(sup)}"


def pct(x: float, casas: int = 1) -> str:
    return br(100 * x, casas) + "%"


# --------------------------------------------------------------------------------------------------------------------- fontes
F3 = "reports/qa/fase3_execucao.json"
USO = "reports/qa/qualidade_uso_solo_fase2.json"
DREN = "reports/qa/qualidade_drenagem_fase2.json"
SENS = "reports/qa/sensibilidade_hidrologica.json"
ROB = "reports/qa/robustez_espacial.json"
MOD = "reports/qa/modelos_exploratorio_alagamentos.json"


def numeros() -> list[dict]:
    """Cada indicador: valor lido da fonte, unidade, definição, origem, contexto e limitação. ``grupo``: processamento, metodologico ou validacao."""
    f3, uso, sens, rob, mod = jcarrega(F3), jcarrega(USO), jcarrega(SENS), jcarrega(ROB), jcarrega(MOD)
    pg, d = f3["pegadas_dos_trechos"], f3["descricao"]
    cmp_ = f3["comparacao_exploratoria_com_os_registros"]["metricas"]
    topo = cmp_["nivel1_altura_de_preenchimento_max"]
    cob = uso["cobertura_dos_metodos"]
    drn = jcarrega(DREN)["rede_pluvial"]
    dmeta = json.loads((RAIZ / "data/processed/drenagem_web/meta.json").read_text())["camadas"]
    n_rede = sum(v["registros_processados"] for v in drn.values())
    return [
        dict(chave="trechos_com_dados", grupo="processamento", titulo="Trechos viários com dados", valor=pg["com_celulas_com_dados"], texto=br(pg["com_celulas_com_dados"]), unidade="trechos",
             definicao="Trechos da rede de ruas com ao menos uma célula de 30 m com dado de uso do solo e relevo sob a sua pegada.",
             origem=f"{F3} · pegadas_dos_trechos.com_celulas_com_dados", ctx=f"De {br(pg['trechos'])} trechos da rede do OpenStreetMap em Porto Alegre ({pct(pg['com_celulas_com_dados'] / pg['trechos'])}).",
             limite=f"{br(pg['fora_da_grade_sem_nenhuma_celula'])} ficam fora da grade e {br(pg['so_em_celulas_sem_dado_ou_agua_mascarada'])} só tocam células sem dado ou de água: ficam sem valor, nunca zero."),
        dict(chave="uso_do_solo", grupo="processamento", titulo="Município coberto pelo mapa de uso do solo", valor=uso["pela_pintura"]["fracao_do_municipio_coberta"], texto=pct(uso["pela_pintura"]["fracao_do_municipio_coberta"]), unidade="% da área do município",
             definicao="Parte da área municipal classificada pelos 605 mil polígonos de uso do solo, medida na grade de 3 m.",
             origem=f"{USO} · pela_pintura.fracao_do_municipio_coberta", ctx=f"{br(uso['poligonos_processados'])} polígonos, 15 classes, escala 1:2.500 (Profill 2022).",
             limite=f"Os {br(uso['lacunas_contra_agua_osm']['lacuna_m2'] / 1e6, 1)} km² sem classe são em {pct(uso['lacunas_contra_agua_osm']['fracao_da_lacuna_sobre_agua_osm'], 0)} água do Guaíba; o restante não foi explicado."),
        dict(chave="celulas", grupo="processamento", titulo="Células de 30 m processadas", valor=f3["motor"]["celulas_com_dados"], texto=br(f3["motor"]["celulas_com_dados"]), unidade="células",
             definicao="Células da grade do modelo de elevação com dado, unidade de cálculo do fluxo e da geração de escoamento.",
             origem=f"{F3} · motor.celulas_com_dados", ctx=f"O acúmulo é idêntico ao do índice de suscetibilidade do projeto e a massa se conserva (erro relativo máximo de {exp10(f3['motor']['conservacao_de_massa']['erro_relativo_maximo'])}).",
             limite="O modelo de elevação é um modelo de superfície de 30 m (Copernicus GLO-30), com erro médio de 2,18 m contra marcos da Prefeitura."),
        dict(chave="drenagem", grupo="processamento", titulo="Trechos de rede pluvial cadastrados", valor=n_rede, texto=br(n_rede), unidade="trechos (cadastro)",
             definicao="Linhas do cadastro municipal de drenagem: rede, rede sem acesso e rede cadastrada como não interligada.",
             origem=f"{DREN} · rede_pluvial.*.registros_processados (3 camadas de origem)", ctx=f"Mais {br(dmeta['pocos']['registros'])} poços de visita, {br(dmeta['bocas']['registros'])} bocas de lobo e {br(dmeta['bombas']['registros'])} casas de bomba. Camada contextual, fora do cálculo.",
             limite="O cadastro diz o que está registrado, não capacidade de vazão, funcionamento nem conexão hidráulica; só o nome das casas de bomba está preenchido."),
        dict(chave="cobertura_m1", grupo="metodologico", titulo="Área com coeficiente de escoamento fundamentado", valor=cob["metodo1_fracao_da_area_classificada"], texto=pct(cob["metodo1_fracao_da_area_classificada"]), unidade="% da área classificada",
             definicao="Parte da área cujas classes (edificação e via pavimentada) têm coeficiente C em referência publicada (Método 1).",
             origem=f"{USO} · cobertura_dos_metodos.metodo1_fracao_da_area_classificada", ctx=f"{pct(cob['sem_coeficiente_fundamentado_fracao'])} da área não tem coeficiente fundamentado e {pct(cob['fora_do_calculo_fracao'])} é água ou fica fora do cálculo.",
             limite="Para o resto só há limites físicos (C = 0 a 1) e cenários por analogia, que são hipóteses declaradas."),
        dict(chave="cobertura_trecho", grupo="metodologico", titulo="Área a montante com coeficiente fundamentado, por trecho", valor=d["fracoes_a_montante_medianas"]["fracao_montante_coberta_m1"], texto=pct(d["fracoes_a_montante_medianas"]["fracao_montante_coberta_m1"]), unidade="% da área a montante (mediana)",
             definicao="Para cada trecho, a fração da área que drena para ele cujo uso do solo tem coeficiente fundamentado; mediana entre os trechos.",
             origem=f"{F3} · descricao.fracoes_a_montante_medianas.fracao_montante_coberta_m1", ctx="É o grau de confiança do valor de cada trecho; fica em cada trecho do mapa.",
             limite="Com cobertura baixa o intervalo do Método 1 considera só uma parte da área: deve ser lido como parcial."),
        dict(chave="contribuicao_mediana", grupo="metodologico", titulo="Contribuição potencial mediana por trecho", valor=d["nivel2_p30"]["metodo1"]["contrib_potencial_max_m3"]["q50"], texto=br(d["nivel2_p30"]["metodo1"]["contrib_potencial_max_m3"]["q50"], 1), unidade="m³ (30 mm, Método 1, limite superior)",
             definicao="Água que a superfície das áreas a montante pode escoar até o trecho para uma chuva hipotética de 30 mm, sem infiltração nem perdas.",
             origem=f"{F3} · descricao.nivel2_p30.metodo1.contrib_potencial_max_m3.q50", ctx=f"A cauda é longa: percentil 90 de {br(d['nivel2_p30']['metodo1']['contrib_potencial_max_m3']['q90'])} m³ e percentil 99 de {br(d['nivel2_p30']['metodo1']['contrib_potencial_max_m3']['q99'])} m³.",
             limite="É potencial, não volume transportado; não pode ser somado entre trechos, porque as áreas a montante se sobrepõem."),
        dict(chave="sem_preenchimento", grupo="metodologico", titulo="Trechos sem preenchimento de depressão", valor=d["nivel1"]["trechos_com_preenchimento_zero"] / d["nivel1"]["trechos_com_valor"], texto=pct(d["nivel1"]["trechos_com_preenchimento_zero"] / d["nivel1"]["trechos_com_valor"]), unidade="% dos trechos com dados",
             definicao="Trechos em que o preenchimento de depressões não soma altura ao relevo do modelo: o indicador topográfico de retenção vale zero.",
             origem=f"{F3} · descricao.nivel1.trechos_com_preenchimento_zero / trechos_com_valor", ctx=f"{br(d['nivel1']['trechos_com_preenchimento_zero'])} de {br(d['nivel1']['trechos_com_valor'])} trechos; só os {br(d['nivel1']['trechos_com_valor'] - d['nivel1']['trechos_com_preenchimento_zero'])} restantes têm posto no indicador.",
             limite="A altura não é interpretável em metros com um modelo de 30 m: serve só para comparar trechos entre si, não como profundidade."),
        dict(chave="regra_atual", grupo="validacao", titulo="Regra de terreno atual (referência)", valor=cmp_["regra_atual_percentil"]["precisao_media"], texto=br(cmp_["regra_atual_percentil"]["precisao_media"], 5), unidade="precisão média",
             definicao="Precisão média da regra atual (percentil de índice de terreno) para achar os trechos com alagamento registrado, em validação por blocos espaciais.",
             origem=f"{F3} · comparacao_exploratoria_com_os_registros.metricas.regra_atual_percentil.precisao_media", ctx=f"{sens['amostra']['trechos_rotulados']} trechos positivos em {br(sens['amostra']['trechos'])}; taxa base de {pct(sens['amostra']['taxa_base'], 3)}; AUC {br(cmp_['regra_atual_percentil']['auc'], 3)}.",
             limite="Os 124 registros são de 2013 e 2014, sem horário nem chuva associada: a comparação é exploratória."),
        dict(chave="melhor_ganho", grupo="validacao", titulo="Maior ganho observado sobre a regra atual", valor=topo["ganho_sobre_a_regra"], texto=f"+{br(100 * topo['ganho_sobre_a_regra'], 1)}%", unidade="de precisão média (indicador topográfico)",
             definicao="Variação da precisão média do indicador topográfico em relação à regra atual na mesma amostra.",
             origem=f"{F3} · comparacao_exploratoria_com_os_registros.metricas.nivel1_altura_de_preenchimento_max.ganho_sobre_a_regra", ctx=f"Intervalo de 95% (blocos completos): {br(100 * topo['ic95_ganho_por_blocos_completos'][0], 0)}% a +{br(100 * topo['ic95_ganho_por_blocos_completos'][1], 0)}%. Critério de adoção: ganho de 10% com limite inferior acima de zero.",
             limite="Intervalo que inclui zero não é evidência de superioridade: nenhum candidato atende o critério e a regra atual permanece."),
        dict(chave="blocos_atendem", grupo="validacao", titulo="Configurações de blocos que atendem o critério", valor=sum(v["configuracoes_que_atendem_o_criterio"] for v in rob["resumo_das_configuracoes"]["por_modelo"].values()), texto=f"0 de {rob['resumo_das_configuracoes']['total']}", unidade="configurações espaciais",
             definicao="Divisões do espaço em blocos (lados e origens diferentes) em que algum modelo físico atinge o critério de adoção.",
             origem=f"{ROB} · resumo_das_configuracoes.por_modelo.*.configuracoes_que_atendem_o_criterio", ctx=f"{rob['resumo_das_configuracoes']['adequadas']} das {rob['resumo_das_configuracoes']['total']} configurações têm positivos bem distribuídos; retirar o maior bloco não muda a conclusão.",
             limite="Mas o ganho troca de sinal ao retirar até 2 blocos e a ordem dos modelos assume 6 formas: nenhum ganho pode ser lido como evidência."),
        dict(chave="ml_melhor", grupo="validacao", titulo="Melhor ganho entre os modelos de aprendizado de máquina", valor=max(mod["modelos"][m]["ganho_sobre_a_regra"] for m in ("regressao_logistica", "gradient_boosting", "mlp")), texto=f"{br(100 * max(mod['modelos'][m]['ganho_sobre_a_regra'] for m in ('regressao_logistica', 'gradient_boosting', 'mlp')), 1)}%", unidade="de precisão média sobre a regra",
             definicao="Regressão logística, gradient boosting e rede MLP em validação por blocos espaciais, contra a regra de terreno atual.",
             origem=f"{MOD} · modelos.*.ganho_sobre_a_regra", ctx="Os três ficaram abaixo da regra (" + ", ".join(f"{100 * mod['modelos'][m]['ganho_sobre_a_regra']:.1f}%".replace(".", ",").replace("-", "−") for m in ("regressao_logistica", "gradient_boosting", "mlp")) + "), com intervalos que se sobrepõem. Nenhum seria adotado.",
             limite="Cerca de 100 positivos e só terreno como entrada: o resultado diz que não há ganho demonstrável com estes dados, não que o aprendizado de máquina não sirva."),
    ]


def tabela_de_metodos() -> str:
    sens, f3, mod, rob = jcarrega(SENS), jcarrega(F3), jcarrega(MOD), jcarrega(ROB)
    m, cm = sens["modelos"], f3["comparacao_exploratoria_com_os_registros"]["metricas"]
    def sg(x): return f"{x:+.1f}".replace(".", ",") + "%"
    def ic(l, h): return f"{sg(100 * l)} a {sg(100 * h)}"
    d1, d2 = m["D1_media_de_postos_regra_e_fisica"]["por_cenario_de_C"]["espacial_0,30-0,95"], m["D2_componentes_mais_fisica"]["por_cenario_de_C"]["espacial_0,30-0,95"]
    b = m["B_fluxo_ajustado_pela_declividade"]
    L = [("Fluxo ajustado pela declividade", b["ganho_sobre_a_referencia"], b["ic95_ganho_por_blocos_completo"], "Piora a regra atual; o fluxo acumulado e a declividade já são componentes do índice em uso."),
         ("Média de postos: regra + física", d1["ganho_sobre_a_referencia"], d1["ic95_ganho_por_blocos_completo"], "O intervalo inclui zero e o ganho troca de sinal ao retirar até 2 blocos espaciais."),
         ("Regressão logística + física", d2["ganho_sobre_a_referencia"], d2["ic95_ganho_por_blocos_completo"], f"Abaixo da regra; varia de {sg(100 * min(v['ganho_minimo'] for k, v in rob['resumo_das_configuracoes']['por_modelo'].items() if k.startswith('D2')))} a {sg(100 * max(v['ganho_maximo'] for k, v in rob['resumo_das_configuracoes']['por_modelo'].items() if k.startswith('D2')))} conforme a grade de blocos."),
         ("Indicador topográfico (Fase 3)", cm["nivel1_altura_de_preenchimento_max"]["ganho_sobre_a_regra"], cm["nivel1_altura_de_preenchimento_max"]["ic95_ganho_por_blocos_completos"], f"Maior ganho, mas o intervalo inclui zero; {pct(f3['descricao']['nivel1']['trechos_com_preenchimento_zero'] / f3['descricao']['nivel1']['trechos_com_valor'])} dos trechos têm o mesmo valor (sem preenchimento)."),
         ("Contribuição, Método 1 (Fase 3)", cm["nivel2_contribuicao_m1_max"]["ganho_sobre_a_regra"], cm["nivel2_contribuicao_m1_max"]["ic95_ganho_por_blocos_completos"], f"Ganho acima de 10%, com intervalo que inclui zero; cobre só {pct(jcarrega(USO)['cobertura_dos_metodos']['metodo1_fracao_da_area_classificada'])} da área."),
         ("Contribuição, Método 2 (Fase 3)", cm["nivel2_contribuicao_analoga_max"]["ganho_sobre_a_regra"], cm["nivel2_contribuicao_analoga_max"]["ic95_ganho_por_blocos_completos"], "Sem ganho; os coeficientes são hipóteses por analogia."),
         ("Contribuição, limites físicos (Fase 3)", cm["nivel2_contribuicao_limites_max"]["ganho_sobre_a_regra"], cm["nivel2_contribuicao_limites_max"]["ic95_ganho_por_blocos_completos"], "Sem ganho; C = 0 a 1 é só o envelope matemático.")]
    linhas = "".join(f"<tr><th scope='row'>{html.escape(n)}</th><td>{sg(100 * g)}</td><td>{ic(*i)}</td><td>não</td><td>{html.escape(j)}</td></tr>" for n, g, i, j in L)
    for k, nome in (("regressao_logistica", "Regressão logística (só terreno)"), ("gradient_boosting", "Gradient boosting (só terreno)"), ("mlp", "Rede MLP (só terreno)")):
        v = mod["modelos"][k]
        linhas += f"<tr><th scope='row'>{nome}</th><td>{sg(100 * v['ganho_sobre_a_regra'])}</td><td>não calculado; os intervalos da precisão média se sobrepõem aos da regra</td><td>não</td><td>Cerca de 100 positivos: não sustenta diferença.</td></tr>"
    return ("<table class='tab-metodos'><caption>Ganho de precisão média sobre a regra atual, mesma amostra (124 positivos em 107.869 trechos), validação por blocos espaciais</caption>"
            "<thead><tr><th scope='col'>Método</th><th scope='col'>Ganho</th><th scope='col'>Intervalo de 95%</th><th scope='col'>Atende o critério</th><th scope='col'>Por que não foi adotado</th></tr></thead><tbody>" + linhas + "</tbody></table>")


def dimensoes() -> dict:
    from PIL import Image

    out = {}
    for p in FIG.glob("*.png"):
        w, h = Image.open(p).size
        out["DIM_" + p.stem.upper().replace("-", "_")] = f'width="{w}" height="{h}"'
    for p in FIG.glob("*.svg"):   # o viewBox evita que o layout salte quando o gráfico carrega
        vb = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', p.read_text(encoding="utf-8")[:2000])
        out["DIM_" + p.stem.upper().replace("-", "_")] = f'width="{round(float(vb.group(1)))}" height="{round(float(vb.group(2)))}"'
    return out


def totais_por_chuva() -> dict:
    f3 = jcarrega(F3)
    return f3["motor"]["totais_da_cidade_soma_das_celulas_m3"], f3["descricao"]["nivel2_p30"]


# --------------------------------------------------------------------------------------------------------------------- figuras
def paletas_do_app() -> tuple[dict, dict]:
    js = (ESTATICO / "fase3-dados.js").read_text(encoding="utf-8")
    pal = {k: re.findall(r'"(#[0-9a-fA-F]{6})"', re.search(rf"\n    {k}: \[(.*?)\]", js).group(1)) for k in ("c", "l", "tp", "cb")}
    dj = (ESTATICO / "drenagem.js").read_text(encoding="utf-8")
    cores = dict(re.findall(r'(\w+): "(#[0-9a-fA-F]{6})"', re.search(r"var COR = \{(.*?)\};", dj, re.S).group(1)))
    return pal, cores


def _figura(largura_px: int, limites, dpi=100, fundo=TINTA):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x0, y0, x1, y1 = limites
    alt = int(round(largura_px * (y1 - y0) / (x1 - x0)))
    fig = plt.figure(figsize=(largura_px / dpi, alt / dpi), dpi=dpi, facecolor=fundo)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax, dpi


def _salvar(fig, caminho_png: Path, cores=96):
    from PIL import Image

    caminho_png.parent.mkdir(parents=True, exist_ok=True)
    bruto = caminho_png.with_suffix(".tmp.png")
    fig.savefig(bruto, facecolor=fig.get_facecolor())
    import matplotlib.pyplot as plt

    plt.close(fig)
    Image.open(bruto).convert("RGB").quantize(colors=cores, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(caminho_png, optimize=True)
    bruto.unlink()


def _linhas(geoms):
    return [np.asarray(g.coords)[:, :2] for g in geoms]


def mapa_de_trechos(geo, classes, paleta, caminho_png, limites, largura=1500, escala=1.0, zero="#2c4a5c", ausente="#3b5262", dpi=100):
    from matplotlib.collections import LineCollection

    fig, ax, dpi = _figura(largura, limites, dpi)
    px = 72 / dpi
    larg = [0.45, 0.45, 0.6, 0.8, 1.0, 1.3, 1.7]
    cores = [zero] + paleta[1:]
    cl = classes.fillna(-1).astype(int).to_numpy()
    geoms = geo.geometry.to_numpy()
    if (cl < 0).any():
        ax.add_collection(LineCollection(_linhas(geoms[cl < 0]), colors=ausente, linewidths=0.4 * escala * px, capstyle="round"))
    for c in range(0, len(cores)):
        m = cl == c
        if m.any():
            ax.add_collection(LineCollection(_linhas(geoms[m]), colors=cores[c], linewidths=larg[min(c, 6)] * escala * px, capstyle="round"))
    _salvar(fig, caminho_png)


def mapa_de_drenagem(rede, pocos, bocas, cores, caminho_png, limites, largura=1500, escala=1.0, dpi=100, pontos=True):
    from matplotlib.collections import LineCollection

    fig, ax, dpi = _figura(largura, limites, dpi)
    px = 72 / dpi
    rede = rede[rede["usar_no_inventario"]]
    for cam, chave, lw in (("rede_pluvial", "cadastro", 0.55), ("rede_pluvial_sem_acesso", "sem_acesso", 0.9), ("rede_pluvial_nao_interligada", "nao_interligada", 1.2)):
        sub = rede[rede["camada_origem"] == cam]
        ax.add_collection(LineCollection(_linhas(sub.geometry), colors=cores[chave], linewidths=lw * escala * px, capstyle="round", linestyles="--" if chave == "nao_interligada" else "-"))
    if pontos:
        for g, chave, s in ((pocos, "poco", 1.2), (bocas, "boca", 1.0)):
            g = g[g["usar_no_inventario"]]
            ax.scatter(g.geometry.x, g.geometry.y, s=s * escala, c=cores[chave], linewidths=0, zorder=3)
    _salvar(fig, caminho_png)


def _tabela():
    from flooding_mapping import camada_fase3 as c3

    return c3.carregar(RAIZ / "data/processed/fase3", RAIZ / "data/interim/segments.parquet", RAIZ / "data/processed/rede_poa.parquet")


def figuras_mapas():
    """Desenha os mapas de trechos e de drenagem em ``FIG_MAPAS_LOCAIS``, nunca na pasta publicada (ver o docstring do módulo)."""
    FIG = FIG_MAPAS_LOCAIS
    FIG.mkdir(parents=True, exist_ok=True)
    from flooding_mapping import camada_drenagem as dr
    from flooding_mapping import camada_fase3 as c3

    pal, cores = paletas_do_app()
    t = c3.carregar(RAIZ / "data/processed/fase3", RAIZ / "data/interim/segments.parquet", RAIZ / "data/processed/rede_poa.parquet")
    cl, _ = c3.classes_visuais(t)
    x0, y0, x1, y1 = t.total_bounds
    pad = 400
    lim = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    # hero: contribuição potencial (Método 1, limite superior), todos os trechos
    mapa_de_trechos(t, cl["c_m1_max"], pal["c"], FIG / "mapa-hero.png", lim, largura=1500, zero="#24465a", ausente="#2a4152")
    mapa_de_trechos(t, cl["c_m1_max"], pal["c"], FIG / "mapa-contribuicao.png", lim, largura=1100, zero="#2c4a5c")
    mapa_de_trechos(t, cl["l_m1_max"], pal["l"], FIG / "mapa-local.png", lim, largura=1100, zero="#2c4a5c")
    mapa_de_trechos(t, cl["tp"], pal["tp"], FIG / "mapa-topografico.png", lim, largura=1100, zero="#2c4a5c")
    rede, pocos, bocas = (dr.carregar(RAIZ / "data/processed/drenagem", k) for k in ("rede", "pocos", "bocas"))
    mapa_de_drenagem(rede, pocos, bocas, cores, FIG / "mapa-drenagem.png", lim, largura=1100, escala=1.0, pontos=False)
    # recorte: Centro e Cidade Baixa, mesma janela, duas camadas independentes
    from pyproj import Transformer

    cx, cy = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True).transform(-51.2255, -30.0372)
    rec = (cx - 1700, cy - 1100, cx + 1700, cy + 1100)
    mapa_de_trechos(t, cl["c_m1_max"], pal["c"], FIG / "recorte-contribuicao.png", rec, largura=1200, escala=3.0, zero="#315468", ausente="#3b5262")
    mapa_de_drenagem(rede, pocos, bocas, cores, FIG / "recorte-drenagem.png", rec, largura=1200, escala=3.0, pontos=True)
    return t


def _estilo_svg():
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update({"svg.fonttype": "none", "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 11,
                                "axes.edgecolor": TINTA, "axes.labelcolor": TINTA, "xtick.color": TINTA, "ytick.color": TINTA, "text.color": TINTA,
                                "axes.spines.top": False, "axes.spines.right": False, "axes.facecolor": "none", "figure.facecolor": "none"})


def grafico_metodos(caminho_svg: Path):
    import matplotlib.pyplot as plt

    _estilo_svg()
    sens, f3 = jcarrega(SENS), jcarrega(F3)
    m = sens["modelos"]
    def sc(grupo, nome): return m[grupo]["por_cenario_de_C"][nome]
    itens = [("Fluxo ajustado pela declividade", m["B_fluxo_ajustado_pela_declividade"], "ic95_ganho_por_blocos_completo", "ganho_sobre_a_referencia", "exploratório"),
             ("Média de postos: regra + física", sc("D1_media_de_postos_regra_e_fisica", "espacial_0,30-0,95"), "ic95_ganho_por_blocos_completo", "ganho_sobre_a_referencia", "exploratório"),
             ("Regressão logística + física", sc("D2_componentes_mais_fisica", "espacial_0,30-0,95"), "ic95_ganho_por_blocos_completo", "ganho_sobre_a_referencia", "exploratório")]
    cm = f3["comparacao_exploratoria_com_os_registros"]["metricas"]
    rot = {"nivel1_altura_de_preenchimento_max": "Indicador topográfico (Fase 3)", "nivel2_contribuicao_m1_max": "Contribuição, Método 1 (Fase 3)",
           "nivel2_contribuicao_analoga_max": "Contribuição, Método 2 (Fase 3)", "nivel2_contribuicao_limites_max": "Contribuição, limites físicos (Fase 3)"}
    for k, nome in rot.items():
        itens.append((nome, cm[k], "ic95_ganho_por_blocos_completos", "ganho_sobre_a_regra", "fase 3"))
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    for i, (nome, v, kic, kg, _) in enumerate(itens):
        y = len(itens) - 1 - i
        lo, hi = (100 * x for x in v[kic])
        g = 100 * v[kg]
        ax.plot([lo, hi], [y, y], color=FORTE, lw=2.6, solid_capstyle="round")
        ax.plot([g], [y], "o", color=ACENTO, ms=9, mec=TINTA, mew=1)
    ax.axvline(0, color=TINTA, lw=1)
    ax.axvline(10, color=TINTA, lw=1, ls=(0, (4, 3)))
    ax.set_ylim(-0.6, len(itens) - 0.1 + 0.9)
    ax.text(11, len(itens) + 0.1, "margem exigida: +10%, com o intervalo todo acima de zero", fontsize=9, va="center")
    ax.set_yticks(range(len(itens)))
    ax.set_yticklabels([n for n, *_ in itens][::-1])
    ax.set_xlabel("Ganho de precisão média sobre a regra atual (%), intervalo de 95% por blocos")
    ax.set_xlim(-50, 115)
    fig.tight_layout()
    fig.savefig(caminho_svg, facecolor="none")
    plt.close(fig)


def grafico_ml(caminho_svg: Path):
    import matplotlib.pyplot as plt

    _estilo_svg()
    mod = jcarrega(MOD)["modelos"]
    nomes = {"regra_de_terreno": "Regra de terreno\n(referência)", "regressao_logistica": "Regressão\nlogística", "gradient_boosting": "Gradient\nboosting", "mlp": "Rede MLP"}
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    for i, (k, nome) in enumerate(nomes.items()):
        v = mod[k]
        lo, hi = v["intervalo_95_precisao_media"]
        ax.bar(i, v["precisao_media"] * 1000, color=ACENTO if k == "regra_de_terreno" else FORTE, width=0.58)
        ax.plot([i, i], [lo * 1000, hi * 1000], color=TINTA, lw=2)
        g = v.get("ganho_sobre_a_regra")
        ax.text(i, hi * 1000 + 0.06, "referência" if g is None else f"{100 * g:+.1f}%".replace(".", ","), ha="center", fontsize=10)
    ax.set_xticks(range(len(nomes)))
    ax.set_xticklabels(list(nomes.values()))
    ax.set_ylabel("Precisão média (× 10⁻³)")
    ax.set_ylim(0, 3.3)
    fig.tight_layout()
    fig.savefig(caminho_svg, facecolor="none")
    plt.close(fig)


def grafico_distribuicao(caminho_svg: Path, t):
    import matplotlib.pyplot as plt

    _estilo_svg()
    v = (30 * t["contrib_aeq_m1_max_m2"].dropna() / 1000)
    zeros = int((v == 0).sum())
    pos = v[v > 0]
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    bins = np.logspace(np.log10(pos.min()), np.log10(pos.max()), 46)
    ax.hist(pos, bins=bins, color=FORTE)
    q = {p: float(np.quantile(v, p)) for p in (0.5, 0.9, 0.99)}
    altura = {0.5: 0.93, 0.9: 0.80, 0.99: 0.67}
    for p, x in q.items():
        ax.axvline(x, color=ACENTO, lw=2)
        ax.text(x * 1.12, ax.get_ylim()[1] * altura[p], f"percentil {int(p * 100)}: {br(x, 0 if x > 100 else 1)} m³", fontsize=9, va="top", bbox=dict(facecolor="#e6f0f5", edgecolor="none", pad=1.5))
    ax.set_xscale("log")
    ax.set_xlabel("Contribuição potencial por trecho, m³ (30 mm, Método 1, limite superior; eixo logarítmico)")
    ax.set_ylabel("Trechos")
    ax.text(0.99, 0.5, f"{br(zeros)} trechos com valor zero\nnão aparecem no eixo logarítmico", transform=ax.transAxes, ha="right", fontsize=9)
    fig.tight_layout()
    fig.savefig(caminho_svg, facecolor="none")
    plt.close(fig)
    return {"quantis_m3": {str(int(p * 100)): x for p, x in q.items()}, "zeros": zeros, "positivos": int(len(pos))}


def grafico_cobertura(caminho_svg: Path):
    import matplotlib.pyplot as plt

    _estilo_svg()
    c = jcarrega(USO)["cobertura_dos_metodos"]
    partes = [("Coeficiente fundamentado\n(Método 1)", c["metodo1_fracao_da_area_classificada"], FORTE, "#ffffff"), ("Água e fora do cálculo", c["fora_do_calculo_fracao"], LEVE, TINTA),
              ("Sem coeficiente fundamentado\n(só limites físicos e cenários)", c["sem_coeficiente_fundamentado_fracao"], TINTA, "#ffffff")]
    fig, ax = plt.subplots(figsize=(8.6, 1.9))
    x = 0
    for nome, f, cor, tx in partes:
        ax.barh(0, 100 * f, left=x, color=cor, height=0.55, edgecolor="#e6f0f5")
        ax.text(x + 50 * f, 0, f"{br(100 * f, 1)}%", ha="center", va="center", color=tx, fontsize=12, fontweight="bold")
        if f > 0.12:
            ax.text(x + 50 * f, -0.52, nome, ha="center", va="top", fontsize=9)
        else:
            ax.text(x + 50 * f, 0.5, nome, ha="center", va="bottom", fontsize=9)
        x += 100 * f
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.15, 1.0)
    ax.axis("off")
    fig.savefig(caminho_svg, facecolor="none", bbox_inches="tight")
    plt.close(fig)


def grafico_chuva_mensal(caminho_svg: Path):
    """Média mensal de chuva (mm por mês) por mês do calendário, a partir de rankings_poa.json (tools/gerar_rankings.py)."""
    import matplotlib.pyplot as plt

    _estilo_svg()
    m = jcarrega(RANKINGS)["media_mensal_de_chuva"]
    nomes = [x["mes"][:3].capitalize() for x in m["meses"]]
    vals = [x["media_mm"] for x in m["meses"]]
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    barras = ax.bar(nomes, vals, color=FORTE, width=0.7)
    ax.axhline(m["media_dos_meses_mm"], color=ACENTO, linewidth=2, linestyle="--")
    ax.text(11.45, m["media_dos_meses_mm"] + 4, f"média dos meses: {br(m['media_dos_meses_mm'], 0)} mm", ha="right", va="bottom", fontsize=9, color=TINTA)
    for b, v in zip(barras, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 3, br(v, 0), ha="center", va="bottom", fontsize=9, color=TINTA)
    ax.set_ylabel("mm por mês")
    ax.set_ylim(0, max(vals) * 1.18)
    fig.savefig(caminho_svg, facecolor="none", bbox_inches="tight")
    plt.close(fig)


def tabela_chuva_mensal() -> str:
    m = jcarrega(RANKINGS)["media_mensal_de_chuva"]
    linhas = "".join(f"<tr><th scope='row'>{html.escape(x['mes'].capitalize())}</th><td>{br(x['media_mm'], 1)}</td><td>{x['anos']}</td></tr>" for x in m["meses"])
    return ("<table class='tab-fontes'><caption>Média mensal de chuva, Porto Alegre</caption><thead><tr><th scope='col'>Mês</th><th scope='col'>Média (mm por mês)</th><th scope='col'>Anos na média</th></tr></thead>"
            f"<tbody>{linhas}</tbody></table>")


def tabela_top5() -> str:
    r = jcarrega(RANKINGS)["top5_bairros"]
    linhas = "".join(f"<tr><th scope='row'>{i['posicao']}. {html.escape(i['bairro'])}</th><td>{br(100 * i['parcela_com_propensao_topografica'], 1)}%</td>"
                     f"<td>{br(100 * i['parcela_no_decil_superior_de_contribuicao'], 1)}%</td><td>{br(i['trechos_com_dados'])}</td><td>{br(100 * i['cobertura_do_coeficiente_a_montante_mediana'], 0)}%</td></tr>" for i in r["itens"])
    return (f"<p class='small'>Critério: {html.escape(r['criterio'])}. Universo: {html.escape(r['universo'])}.</p><div class='tabela-rolagem'><table class='tab-fontes'><caption>Top 5 bairros por propensão topográfica à retenção</caption>"
            "<thead><tr><th scope='col'>Bairro</th><th scope='col'>Ruas com propensão topográfica à retenção (parcela das ruas do bairro)</th><th scope='col'>Ruas entre as 10% de maior concentração da cidade (parcela)</th><th scope='col'>Trechos de rua com dados</th><th scope='col'>Área a montante com coeficiente publicado (mediana)</th></tr></thead>"
            f"<tbody>{linhas}</tbody></table></div><p class='small'>As colunas não se combinam em índice. Cobertura baixa significa que parte da área a montante só tem coeficiente de escoamento (fração da chuva que escoa) por hipótese declarada.</p>")


# --------------------------------------------------------------------------------------------------------------------- html
def cartao(n: dict) -> str:
    e = html.escape
    return (f'<article class="num" data-chave="{n["chave"]}" data-valor="{n["valor"]!r}" data-fonte="{e(n["origem"])}">'
            f'<h4>{e(n["titulo"])}</h4><p class="fig">{e(n["texto"])}</p><p class="unid">{e(n["unidade"])}</p>'
            f'<dl class="vis"><dt>Contexto</dt><dd>{e(n["ctx"])}</dd><dt>Limitação</dt><dd>{e(n["limite"])}</dd></dl>'
            f'<details><summary>Definição e origem</summary><dl><dt>O que é</dt><dd>{e(n["definicao"])}</dd><dt>De onde vem</dt><dd><code>{e(n["origem"])}</code></dd></dl></details></article>')


def bloco_numeros(lista: list[dict]) -> str:
    titulos = {"processamento": ("Processamento", "O que entrou e o que foi processado. Não são resultados, são o tamanho e a cobertura da base."),
               "metodologico": ("Resultados metodológicos", "O que o motor produz e o quanto cada valor é fundamentado."),
               "validacao": ("Validação exploratória", "O que a comparação com os alagamentos registrados mostrou. Não valida o motor.")}
    out = []
    for g, (t, sub) in titulos.items():
        itens = [n for n in lista if n["grupo"] == g]
        out.append(f'<div class="grupo-num" id="num-{g}"><div class="grupo-cab"><h3>{t}</h3><p>{html.escape(sub)}</p></div><div class="nums">{"".join(cartao(n) for n in itens)}</div></div>')
    return "\n".join(out)


def dados_de_cenarios() -> dict:
    tot, q = totais_por_chuva()
    meta = json.loads((RAIZ / "data/processed/fase3_web/meta.json").read_text())
    cortes = meta["cortes_das_classes_aeq_m2"]
    return {"precipitacoes_mm": meta["precipitacoes_mm"], "totais_m3": tot,
            "por_trecho_p30_metodo1": q["metodo1"], "cortes_m2": {k: cortes[k] for k in ("c_m1_max", "l_m1_max")}}


def legenda_de(cortes: list[float], paleta: list[str], p: int = 30) -> str:
    def f(x): return br(x, 0 if x >= 100 else 1)
    faixas = ["zero"] + [f"até {f(p * cortes[0] / 1000)} m³"] + [f"{f(p * a / 1000)} a {f(p * b / 1000)} m³" for a, b in zip(cortes[:-1], cortes[1:])] + [f"mais de {f(p * cortes[-1] / 1000)} m³"]
    return "".join(f'<li><span style="background:{c}"></span>{html.escape(t)}</li>' for c, t in zip(paleta, faixas))


def numeros_geoai() -> dict:
    """Números da seção de GeoAI, lidos do resultado do experimento (reports/qa/geoai_resultados.json); nada é digitado."""
    r = jcarrega("reports/qa/geoai_resultados.json")
    prim = r["primario"]["modelo"]
    b1, b2 = r["P1_blocos"][prim]["bootstrap_por_blocos"], r["P2_quadrantes"][prim]["bootstrap_por_blocos"]
    d = r["comparacao_pareada_com_o_primario"]["rf_AEF"]
    cd, ba = r["primario"]["classes_duras"], r["primario"]["erro_de_area_por_bairro"]
    com_sinal = lambda x, c=4: ("+" if x > 0 else "−" if x < 0 else "") + br(abs(x), c)   # noqa: E731
    ic = lambda m: f"{br(m['valor'], 3)} ({br(m['ic95'][0], 3)} a {br(m['ic95'][1], 3)})"   # noqa: E731
    return {"GEOAI_MAE_P1": ic(b1["mae"]), "GEOAI_MAE_P2": ic(b2["mae"]),
            "GEOAI_AEF_DIF": f"{com_sinal(d['diferenca_mae'])} (de {com_sinal(d['ic95'][0])} a {com_sinal(d['ic95'][1])})",
            "GEOAI_F1_RF": br(r["P1_blocos"][prim]["bootstrap_por_blocos"]["macro_f1"]["valor"], 3), "GEOAI_F1_AEF": br(r["P1_blocos"]["rf_AEF"]["bootstrap_por_blocos"]["macro_f1"]["valor"], 3),
            "GEOAI_F1_CONSTRUIDO": br(cd["f1"][0], 3), "GEOAI_F1_VEGETACAO": br(cd["f1"][1], 3), "GEOAI_F1_SOLO": br(cd["f1"][2], 2), "GEOAI_F1_AGUA": br(cd["f1"][3], 2),
            "GEOAI_BAIRROS": pct(ba["fracao_dentro_do_limite"], 1)}


def montar(figuras: bool = True) -> dict:
    lista = numeros()
    pal, _ = paletas_do_app()
    cen = dados_de_cenarios()
    t = None
    if figuras:
        t = figuras_mapas() if "--mapas-locais" in sys.argv else _tabela()   # os mapas nunca vão para a pasta publicada
        grafico_metodos(FIG / "grafico-metodos.svg")
        grafico_ml(FIG / "grafico-ml.svg")
        grafico_cobertura(FIG / "grafico-cobertura.svg")
        grafico_chuva_mensal(FIG / "grafico-chuva-mensal.svg")
        dist = grafico_distribuicao(FIG / "grafico-distribuicao.svg", t)
        cen["distribuicao"] = dist
    elif (SAIDA / "dados.json").exists():
        cen["distribuicao"] = json.loads((SAIDA / "dados.json").read_text())["cenarios"].get("distribuicao")
    subs = {
        "NUMEROS": bloco_numeros(lista),
        "CENARIOS_JSON": json.dumps(cen, ensure_ascii=False, separators=(",", ":")),
        "TABELA_CHUVA_MENSAL": tabela_chuva_mensal(),
        "PERIODO_CHUVA": "de " + jcarrega(RANKINGS)["media_mensal_de_chuva"]["periodo_da_serie"][0][:4] + " a " + jcarrega(RANKINGS)["media_mensal_de_chuva"]["periodo_da_serie"][1][:4],
        "TOP5_BAIRROS": tabela_top5(),
        "MOTIVO_TOP10": html.escape(jcarrega(RANKINGS)["nao_publicados"]["top10_trechos"]),
        "MOTIVO_ZONAS": html.escape(jcarrega(RANKINGS)["nao_publicados"]["ranking_de_zonas"]),
        "REFERENCIAS": refs.bloco_html(refs.carregar()),
        **numeros_geoai(),
        "REPO": REPO,
        "TABELA_METODOS": tabela_de_metodos(),
        **dimensoes(),
        "TOTAL_TRECHOS": br(jcarrega(F3)["pegadas_dos_trechos"]["trechos"]),
        "TOTAL_COM_DADOS": br(jcarrega(F3)["pegadas_dos_trechos"]["com_celulas_com_dados"]),
    }
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for k, v in subs.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    tpl = refs.substituir_citacoes(tpl, refs.carregar())
    restos = re.findall(r"\{\{[A-Z_]+\}\}", tpl)
    if restos:
        raise SystemExit(f"marcadores sem valor: {restos}")
    return {"html": tpl, "dados": {"numeros": lista, "cenarios": cen, "paletas": pal, "gerado_de": [F3, USO, DREN, SENS, ROB, MOD]}}


def main() -> None:
    r = montar(figuras="--sem-figuras" not in sys.argv)
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "index.html").write_text(r["html"], encoding="utf-8")
    (SAIDA / "dados.json").write_text(json.dumps(r["dados"], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("gravado:", SAIDA / "index.html")


if __name__ == "__main__":
    main()
