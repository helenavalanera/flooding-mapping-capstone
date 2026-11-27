"""Motor da Fase 3: onde a água de uma chuva PODE chegar, e onde o relevo favorece retê-la. Não calcula volume retido, profundidade, duração nem capacidade de drenagem.

Unidade computacional: a célula de 30 m da grade do DEM. Unidade de apresentação: o trecho viário. Três grandezas distintas, nunca misturadas:

1. VOLUME POTENCIAL GERADO (local): ``V = P x A x C / 1000`` somado nas células da pegada do trecho. Água que a superfície pode gerar ali, de acordo com o uso do solo.
2. CONTRIBUIÇÃO POTENCIAL ASSOCIADA AO TRECHO: o volume potencial gerado sobre a UNIÃO das bacias a montante das células da pegada. Cada célula conta uma vez.
3. VOLUME EFETIVAMENTE TRANSPORTADO: NÃO é calculado. Exigiria infiltração, perdas, capacidade de drenagem, rugosidade e condições de contorno, que não existem nos dados.

Regra de associação (determinística, sem dupla contagem). A pegada do trecho é o conjunto de células que a reta do trecho atravessa (amostrada a cada ``passo`` metros). O acumulado de uma
célula já inclui todo o fluxo a montante; somar células de uma pegada que estão no mesmo caminho de escoamento contaria a mesma água várias vezes. Por isso entram só as células da pegada que NÃO têm outra
célula da pegada a jusante ("células de chegada"). Como cada célula D8 tem um único receptor, as bacias a montante de duas células de chegada são disjuntas: a soma de seus acumulados é exatamente o volume
gerado sobre a união das bacias. Dois caminhos independentes que o trecho cruza somam-se; dois pontos do mesmo caminho contam uma vez.

Os valores por trecho NÃO são somáveis entre trechos: bacias de trechos vizinhos se sobrepõem. O total da cidade existe só como soma das células (cada célula uma vez).

Chuva: ``P`` uniforme em mm, hipotética (cenário, não previsão). Tudo é linear em P, então o motor calcula "áreas equivalentes" ``aeq = soma(A x C)`` em m² uma única vez e o volume é ``P x aeq / 1000``.
Os coeficientes têm três pacotes que NUNCA se somam entre si: ``metodo1`` (fundamentado), ``limites_fisicos`` (C = 0 e C = 1 nas classes que o Método 1 não cobre) e ``referencia_analoga`` (cenários por
analogia; para a classe de jardins e passeios vale SEMPRE o envelope dos cenários de fração, nunca um valor central).

Indicador topográfico (Nível 1): a altura que o preenchimento de depressões soma a cada célula (``preenchido - dem``). É um índice de propensão do relevo à retenção, NÃO é volume armazenável nem
profundidade de alagamento; com o DSM do Copernicus (30 m, erro médio de 2,18 m contra marcos) não é interpretável em metros.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import escoamento
from .fluxo import ArvoreDeFluxo, receptores_d8

PACOTES = ("metodo1", "limites_fisicos", "referencia_analoga")
ROTULO = {"metodo1": "m1", "limites_fisicos": "limites", "referencia_analoga": "analoga"}
CLASSE_JARDINS = "Jardins, Passeios ou Áreas semi urbanizadas"
COLUNAS_PESO = ["aeq_m1_min", "aeq_m1_max", "aeq_limites_min", "aeq_limites_max", "aeq_analoga_min", "aeq_analoga_max",
                "area_m1", "area_limites_com_valor", "area_analoga_com_valor", "area_analoga_sem_valor", "area_fora_do_calculo", "area_sem_classe", "area_total"]
INDICE_PESO = {c: i for i, c in enumerate(COLUNAS_PESO)}
NAO_CALCULADO = {"volume_efetivamente_transportado": "não calculado: exigiria infiltração, perdas, capacidade de drenagem, rugosidade e condições de contorno, que não existem nos dados",
                 "volume_retido_ou_armazenado": "não calculado: a altura de preenchimento é indicador topográfico, não volume armazenável",
                 "profundidade_e_duracao": "não calculadas: não há chuva no tempo, vazão de saída nem registros com início e fim",
                 "conectividade_hidraulica": "não usada: o inventário de drenagem entra só como contexto, sem conexões confirmadas"}
PROIBIDAS_NAS_SAIDAS = ("profundidade", "duracao", "duração", "retido", "retida", "capacidade", "probabilidade", "alagamento_previsto", "previsao", "previsão")


@dataclass(frozen=True)
class GradeRaster:
    origem_x: float
    origem_y: float
    linhas: int
    colunas: int
    celula: float = 30.0

    @property
    def n(self) -> int:
        return self.linhas * self.colunas


def faixas_por_pacote(m1: pd.DataFrame, m2: pd.DataFrame) -> dict:
    """Coefficient interval per class for each package. Method 1 and the scenarios stay separate; Jardins always gets the ENVELOPE of its fraction scenarios."""
    f1 = {r.classe_original: (float(r.c_min), float(r.c_max)) for r in m1.itertuples()}
    fis = m2[m2.cenario.isin(["fisico_inferior", "fisico_superior"])]
    inf, sup = fis[fis.cenario == "fisico_inferior"].set_index("classe_original"), fis[fis.cenario == "fisico_superior"].set_index("classe_original")
    if not ((inf.c_min == 0).all() and (sup.c_max == 1).all() and set(inf.index) == set(sup.index)):
        raise ValueError("os limites físicos devem ser C = 0 (inferior) e C = 1 (superior) nas mesmas classes")
    lim = {c: (0.0, 1.0) for c in inf.index}
    ana = {r.classe_original: (float(r.c_min), float(r.c_max)) for r in m2[m2.cenario == "referencia_analoga"].itertuples()}
    jar = m2[m2.cenario.str.startswith("referencia_analoga_jardins_f")]
    if len(jar):
        ana[CLASSE_JARDINS] = (float(jar.c_min.min()), float(jar.c_max.max()))                  # envelope dos cenários de fração: nenhum valor central
    fora = set(m2[m2.natureza_do_valor == "fora_do_calculo_de_escoamento"].classe_original)
    if set(f1) & set(lim) or set(f1) & set(ana):
        raise ValueError("um cenário não pode redefinir uma classe do Método 1")
    return {"metodo1": f1, "limites_fisicos": lim, "referencia_analoga": ana, "fora_do_calculo": fora}


def matriz_de_pesos(areas: np.ndarray, classes: list, faixas: dict, area_celula: float) -> np.ndarray:
    """(cells x len(COLUNAS_PESO)) weights from the per-class areas (cells x classes, m²). ``aeq`` is sum(A x C) in m²; the ``area_*`` columns are the coverage bookkeeping."""
    W = np.zeros((areas.shape[0], len(COLUNAS_PESO)))
    pos = {c: i for i, c in enumerate(classes)}
    fora = [pos[c] for c in faixas["fora_do_calculo"] if c in pos]
    cobertas_m1 = [pos[c] for c in faixas["metodo1"] if c in pos]
    com_valor_lim = [pos[c] for c in faixas["limites_fisicos"] if c in pos]
    com_valor_ana = [pos[c] for c in faixas["referencia_analoga"] if c in pos]
    for pacote, rot in (("metodo1", "m1"), ("limites_fisicos", "limites"), ("referencia_analoga", "analoga")):
        for k, lado in ((0, "min"), (1, "max")):
            for c, faixa in faixas[pacote].items():
                if c in pos:
                    W[:, INDICE_PESO[f"aeq_{rot}_{lado}"]] += areas[:, pos[c]] * faixa[k]
    W[:, INDICE_PESO["area_m1"]] = areas[:, cobertas_m1].sum(axis=1) if cobertas_m1 else 0.0
    W[:, INDICE_PESO["area_limites_com_valor"]] = areas[:, com_valor_lim].sum(axis=1) if com_valor_lim else 0.0
    W[:, INDICE_PESO["area_analoga_com_valor"]] = areas[:, com_valor_ana].sum(axis=1) if com_valor_ana else 0.0
    W[:, INDICE_PESO["area_fora_do_calculo"]] = areas[:, fora].sum(axis=1) if fora else 0.0
    classificada = areas.sum(axis=1)
    sem_valor_ana = classificada - W[:, INDICE_PESO["area_m1"]] - W[:, INDICE_PESO["area_analoga_com_valor"]] - W[:, INDICE_PESO["area_fora_do_calculo"]]
    W[:, INDICE_PESO["area_analoga_sem_valor"]] = np.maximum(sem_valor_ana, 0.0)
    W[:, INDICE_PESO["area_total"]] = area_celula
    W[:, INDICE_PESO["area_sem_classe"]] = np.maximum(area_celula - classificada, 0.0)
    return W


def pegada_dos_trechos(x0, y0, x1, y1, grade: GradeRaster, passo: float) -> tuple[np.ndarray, np.ndarray]:
    """Unique (segment, flat cell) pairs crossed by each straight segment, sampled every ``passo`` metres plus both ends. Cells cut by a chord shorter than ``passo`` can be missed."""
    x0, y0, x1, y1 = (np.asarray(v, dtype=float) for v in (x0, y0, x1, y1))
    comprimento = np.hypot(x1 - x0, y1 - y0)
    n = np.maximum(2, np.ceil(comprimento / passo).astype(np.int64) + 1)
    seg = np.repeat(np.arange(len(n)), n)
    k = np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)
    t = k / np.repeat(n - 1, n)
    x, y = np.repeat(x0, n) + t * np.repeat(x1 - x0, n), np.repeat(y0, n) + t * np.repeat(y1 - y0, n)
    linha = np.floor((grade.origem_y - y) / grade.celula).astype(np.int64)
    coluna = np.floor((x - grade.origem_x) / grade.celula).astype(np.int64)
    dentro = (linha >= 0) & (linha < grade.linhas) & (coluna >= 0) & (coluna < grade.colunas)
    chave = np.unique(seg[dentro] * grade.n + linha[dentro] * grade.colunas + coluna[dentro])
    return chave // grade.n, chave % grade.n


def celulas_de_chegada(arvore: ArvoreDeFluxo, seg: np.ndarray, cel: np.ndarray) -> np.ndarray:
    """Boolean per (segment, cell) pair: True when no OTHER cell of the same segment lies downstream of it. The catchments of two such cells are disjoint (one receiver per cell)."""
    m = len(seg)
    if m == 0:
        return np.zeros(0, dtype=bool)
    inicio = np.flatnonzero(np.r_[True, seg[1:] != seg[:-1]])
    tamanho = np.diff(np.r_[inicio, m])
    grupo = np.repeat(np.arange(len(inicio)), tamanho)
    k_i = tamanho[grupo]
    rep = np.repeat(np.arange(m), k_i)
    desloc = np.arange(rep.size) - np.repeat(np.cumsum(k_i) - k_i, k_i)
    j = inicio[grupo][rep] + desloc
    a_jusante = arvore.eh_ancestral(cel[j], cel[rep])
    return np.bincount(rep, weights=a_jusante, minlength=m) == 0


def associar_aos_trechos(arvore: ArvoreDeFluxo, n_trechos: int, seg: np.ndarray, cel: np.ndarray, locais: np.ndarray, acumulado: np.ndarray) -> dict:
    """Per segment: local sums over the footprint (each cell once) and contribution sums over the arrival cells only. NaN where the footprint has no cell with data."""
    valido = arvore.valida[cel]
    seg, cel = seg[valido], cel[valido]
    chegada = celulas_de_chegada(arvore, seg, cel)
    K = locais.shape[1]
    local, contrib = np.full((n_trechos, K), np.nan), np.full((n_trechos, K), np.nan)
    tem = np.bincount(seg, minlength=n_trechos) > 0
    for k in range(K):
        local[:, k] = np.where(tem, np.bincount(seg, weights=locais[cel, k], minlength=n_trechos), np.nan)
        contrib[:, k] = np.where(tem, np.bincount(seg[chegada], weights=acumulado[cel[chegada], k], minlength=n_trechos), np.nan)
    return {"local": local, "contribuicao": contrib, "n_celulas_com_dados": np.bincount(seg, minlength=n_trechos), "n_celulas_de_chegada": np.bincount(seg[chegada], minlength=n_trechos)}


def volume_m3(p_mm: float, aeq_m2) -> np.ndarray:
    """Volume (m³) from an equivalent runoff area (m²): V = P x A x C / 1000 with the area already weighted by C. The finite values go through the validated formula;
    a missing area (a segment with no cell with data) stays missing and is never turned into zero."""
    a = np.asarray(aeq_m2, dtype=float)
    saida = np.full(a.shape, np.nan)
    ok = np.isfinite(a)
    saida[ok] = escoamento.volume_gerado_m3(p_mm, a[ok], 1.0)
    return saida if saida.ndim else float(saida)


def executar(dem: np.ndarray, grade: GradeRaster, celulas: pd.DataFrame, classes: dict, m1: pd.DataFrame, m2: pd.DataFrame, trechos: pd.DataFrame,
             precipitacoes_mm=(10, 20, 30), mascara_exutorio: np.ndarray | None = None, passo_m: float | None = None) -> dict:
    """Runs the engine. ``celulas`` has linha, coluna and one ``area_m2__NN`` column per class (``classes`` maps name -> NN). ``trechos`` has segmento_id and x0, y0, x1, y1 in the grid CRS."""
    from .susceptibility import fill_depressions

    if dem.shape != (grade.linhas, grade.colunas):
        raise ValueError("o DEM não tem o formato da grade")
    passo = passo_m or grade.celula / 5
    dem = dem.astype("float64").copy()
    if mascara_exutorio is not None:
        dem[mascara_exutorio] = np.nan                                                      # corpo d'água grande: a água sai do modelo ali (a borda vira exutório)
    preenchido = fill_depressions(dem)
    receptor, valida = receptores_d8(preenchido)
    arvore = ArvoreDeFluxo(receptor, valida)
    altura = np.where(np.isnan(dem), np.nan, preenchido - dem).ravel()
    faixas = faixas_por_pacote(m1, m2)
    nomes = sorted(classes, key=classes.get)
    areas = np.zeros((grade.n, len(nomes)))
    idx = celulas["linha"].to_numpy(np.int64) * grade.colunas + celulas["coluna"].to_numpy(np.int64)
    for j, c in enumerate(nomes):
        areas[idx, j] = celulas[f"area_m2__{classes[c]:02d}"].to_numpy(float)
    W = matriz_de_pesos(areas, nomes, faixas, grade.celula ** 2)
    W[~valida] = 0.0
    acumulado = arvore.acumular(W)
    conservacao = arvore.conservacao(W, acumulado)
    seg, cel = pegada_dos_trechos(trechos["x0"], trechos["y0"], trechos["x1"], trechos["y1"], grade, passo)
    n_tr = len(trechos)
    assoc = associar_aos_trechos(arvore, n_tr, seg, cel, W, acumulado)
    # nível 1: indicador topográfico
    valido_cel = valida[cel]
    s1, c1 = seg[valido_cel], cel[valido_cel]
    h = altura[c1]
    cont = np.bincount(s1, minlength=n_tr)
    h_max = np.full(n_tr, -np.inf)
    np.maximum.at(h_max, s1, h)
    h_max = np.where(cont > 0, h_max, np.nan)
    h_med = np.where(cont > 0, np.bincount(s1, weights=h, minlength=n_tr) / np.maximum(cont, 1), np.nan)
    percentil = pd.Series(h_max).rank(pct=True, method="average").to_numpy() * 100
    base = pd.DataFrame({"segmento_id": trechos["segmento_id"].to_numpy(), "n_celulas_com_dados": assoc["n_celulas_com_dados"], "n_celulas_de_chegada": assoc["n_celulas_de_chegada"]})
    nivel1 = pd.DataFrame({"segmento_id": base.segmento_id, "altura_de_preenchimento_max_m": h_max, "altura_de_preenchimento_media_m": h_med, "propensao_topografica_percentil": percentil,
                           "n_celulas_com_dados": base.n_celulas_com_dados})
    L, C = assoc["local"], assoc["contribuicao"]
    for rot in ("m1", "limites", "analoga"):
        for lado in ("min", "max"):
            base[f"local_aeq_{rot}_{lado}_m2"] = L[:, INDICE_PESO[f"aeq_{rot}_{lado}"]]
            base[f"contrib_aeq_{rot}_{lado}_m2"] = C[:, INDICE_PESO[f"aeq_{rot}_{lado}"]]
    tot = C[:, INDICE_PESO["area_total"]]
    base["area_montante_m2"] = tot
    for nome, col in (("fracao_montante_coberta_m1", "area_m1"), ("fracao_montante_com_valor_limites", "area_limites_com_valor"), ("fracao_montante_com_valor_analoga", "area_analoga_com_valor"),
                      ("fracao_montante_sem_valor_analoga", "area_analoga_sem_valor"), ("fracao_montante_fora_do_calculo", "area_fora_do_calculo"), ("fracao_montante_sem_classe", "area_sem_classe")):
        base[nome] = C[:, INDICE_PESO[col]] / np.where(tot > 0, tot, np.nan)
    longo = []
    for p in precipitacoes_mm:
        for pacote in PACOTES:
            rot = ROTULO[pacote]
            longo.append(pd.DataFrame({"segmento_id": base.segmento_id, "p_mm": float(p), "pacote": pacote,
                                       "v_gerado_local_min_m3": volume_m3(p, base[f"local_aeq_{rot}_min_m2"]), "v_gerado_local_max_m3": volume_m3(p, base[f"local_aeq_{rot}_max_m2"]),
                                       "contrib_potencial_min_m3": volume_m3(p, base[f"contrib_aeq_{rot}_min_m2"]), "contrib_potencial_max_m3": volume_m3(p, base[f"contrib_aeq_{rot}_max_m2"])}))
    nivel2 = pd.concat(longo, ignore_index=True)
    validas = np.flatnonzero(valida)
    lin, col = np.divmod(validas, grade.colunas)
    cel_tab = pd.DataFrame({"linha": lin.astype(np.int32), "coluna": col.astype(np.int32), "altura_de_preenchimento_m": altura[validas].astype("float32")})
    for c in COLUNAS_PESO[:6]:
        cel_tab[c] = W[validas, INDICE_PESO[c]].astype("float32")
        cel_tab["acum_" + c] = acumulado[validas, INDICE_PESO[c]].astype("float32")
    totais = {}
    for p in precipitacoes_mm:
        totais[str(p)] = {pk: {"min_m3": float(volume_m3(p, W[valida, INDICE_PESO[f"aeq_{ROTULO[pk]}_min"]].sum())), "max_m3": float(volume_m3(p, W[valida, INDICE_PESO[f"aeq_{ROTULO[pk]}_max"]].sum()))} for pk in PACOTES}
    relatorio = {"celulas_com_dados": int(valida.sum()), "celulas_mascaradas_como_exutorio": int(0 if mascara_exutorio is None else mascara_exutorio.sum()), "exutorios": int(len(arvore.exutorios())),
                 "conservacao_de_massa": {"erro_relativo_maximo": conservacao["erro_relativo_maximo"], "colunas": COLUNAS_PESO}, "trechos": int(n_tr), "trechos_com_pegada_valida": int((assoc["n_celulas_com_dados"] > 0).sum()),
                 "celulas_da_pegada_por_trecho_mediana": float(np.median(assoc["n_celulas_com_dados"][assoc["n_celulas_com_dados"] > 0])) if (assoc["n_celulas_com_dados"] > 0).any() else 0.0,
                 "totais_da_cidade_soma_das_celulas_m3": totais, "faixas_de_coeficiente_por_pacote": {k: ({c: list(v) for c, v in faixas[k].items()} if k != "fora_do_calculo" else sorted(faixas[k])) for k in faixas},
                 "precipitacoes_mm": [float(p) for p in precipitacoes_mm], "passo_da_pegada_m": passo, "celula_m": grade.celula, "nao_calculado": NAO_CALCULADO}
    return {"nivel1": nivel1, "base": base, "nivel2": nivel2, "celulas": cel_tab, "relatorio": relatorio, "arvore": arvore, "pesos": W, "acumulado": acumulado, "altura": altura, "preenchido": preenchido, "pegada": (seg, cel)}
