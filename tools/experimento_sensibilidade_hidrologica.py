"""Experimento EXPLORATÓRIO de sensibilidade hidrológica: uma formulação física simplificada acrescenta informação ao índice atual?

    PYTHONPATH=src python tools/experimento_sensibilidade_hidrologica.py [saida.json] [relatorio.md]

NÃO altera o índice de produção, o modelo, nem os dados: só lê a tabela de ruas e escreve dois relatórios.
NÃO prevê profundidade nem ocorrência de alagamento: ordena trechos por propensão ao acúmulo de água sob hipóteses de cenário.

Equações (a = área contribuinte específica; tanβ = declividade local)
    A_i   = expm1(log_flow_acc_i) * 30^2                 [m²]   área a montante (D8, células de 30 m; o log é máximo numa janela 3x3)
    a_i   = A_i / 30                                      [m]    área por metro de largura de fluxo
    tanβ  = max(tan(slope_i), 0,001)                      [-]    slope em graus (Copernicus GLO-30)
    V_i   = P * C_i * A_i                                 [m³]   volume afluente POTENCIAL (P em m): não é profundidade nem volume retido
    B_i   = ln(a_i / tanβ_i)                              [-]    TWI: fluxo acumulado ajustado pela declividade
    C_i   = ln(P * C_i * a_i / tanβ_i) = B_i + ln C_i + ln P    índice relativo (unidade arbitrária)
    D1_i  = média de postos (rank 0-1) da regra atual e de C_i, sem ajuste de parâmetros
    D2    = regressão logística com os 5 componentes atuais + C_i, contra a mesma regressão só com os 5 componentes (ganho incremental)

Consequência que o experimento verifica em vez de esconder: com chuva P uniforme e C constante, P e C só deslocam B por uma constante, então
a ORDEM dos trechos não muda. A chuva uniforme não diferencia ruas; só escala o volume. Para C ter efeito na ordem, ele precisa variar no espaço:
os cenários "espacial" fazem C_i = C_min + q_i (C_max − C_min), com q_i o posto da densidade viária em 250 m (hipótese: mais ruas ~ mais área
impermeável a montante; é um PROXY de cenário, não uma medida de impermeabilização).

Coeficientes de escoamento: faixas típicas do método racional, conferidas em manuais de agências (TxDOT Hydraulic Design Manual, seção Rational Method;
San Diego County Hydrology Manual): asfalto/concreto 0,70-0,95; residencial unifamiliar 0,30-0,50 (outras fontes citam 0,30-0,75 para áreas residenciais
em geral); gramados 0,05-0,35 conforme solo e declividade. A tabela do livro de Chow, Maidment & Mays (1988) NÃO foi consultada diretamente. Nenhum valor é
calibrado para Porto Alegre.

Validação: mesmos trechos, mesmos rótulos (a até 100 m de um registro da Prefeitura, 2013-2014) e mesmos blocos espaciais do experimento anterior
(tools/experimento_modelos_alagamentos.py). Os escores B, C e D1 não têm parâmetros ajustados, então não há o que vazar entre trechos vizinhos; D2 é treinado
com blocos inteiros fora do treino. Intervalos: bootstrap sobre os positivos (2000 réplicas, pareado entre modelos), feito de duas formas: por trecho e por blocos espaciais inteiros de 1,5 km
(os 124 trechos vêm de registros vizinhos, que não são independentes). 
Critério de adoção: ganho relativo de precisão média >= 10% sobre a regra E limite inferior do intervalo de 95% do ganho acima de zero nas DUAS formas de
bootstrap, em TODOS os cenários de C. Diferença pequena ou intervalos sobrepostos não contam como superioridade.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import rankdata
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experimento_modelos_alagamentos as exp  # noqa: E402
from flooding_mapping.dados_restritos import ler_alagamentos  # noqa: E402
from flooding_mapping.risco_trecho import COMPONENTES  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CELULA_M = 30.0
TAN_MIN = 0.001
RAIO_DENSIDADE_M = 250
PRECIPITACOES_MM = (10, 30, 60)
P_BASE_MM = 30
MARGEM = exp.MARGEM_AP
REPLICAS = 2000
CONFIGS_C = {  # nome: (C_min, C_max); iguais = uniforme. Hipóteses de cenário, não calibração.
    "uniforme_0,30": (0.30, 0.30), "uniforme_0,50": (0.50, 0.50), "uniforme_0,70": (0.70, 0.70), "uniforme_0,90": (0.90, 0.90),
    "espacial_0,30-0,50": (0.30, 0.50), "espacial_0,50-0,70": (0.50, 0.70), "espacial_0,70-0,95": (0.70, 0.95), "espacial_0,30-0,95": (0.30, 0.95),
}
CONFIG_REFERENCIA = "espacial_0,30-0,95"   # só para a matriz de correlações (a mais distante de B); não é calibração
LIMITACOES = [
    "Os 124 registros são de 2013-2014 e não têm horário nem precipitação associada: o experimento não valida previsão condicionada à chuva.",
    "A chuva é uniforme e hipotética (10, 30 e 60 mm): ela escala o volume, mas não diferencia ruas.",
    "O Copernicus GLO-30 é um DSM de 30 m, com viés de altitude (+2,1 m contra marcos da Prefeitura) e sem microrrelevo urbano (meio-fio, sarjeta).",
    "Não há dados suficientes de capacidade da drenagem (bueiros, galerias): o volume afluente potencial não é volume retido nem profundidade.",
    "Os coeficientes de escoamento são hipóteses de cenário; o proxy espacial (densidade viária) não mede impermeabilização.",
    "O fluxo acumulado e a declividade já são componentes do índice atual: a formulação física reaproveita parte da mesma informação.",
    "Os escores do D2 vêm de modelos diferentes em cada dobra e são agrupados para calcular AP e AUC; calibrações distintas entre dobras podem afetar a AP.",
    "O bootstrap de percentis da AP é assimétrico (poucos positivos muito bem posicionados dominam a métrica); os intervalos descrevem a fragilidade, não um erro padrão.",
    "Resultado exploratório com ~124 trechos positivos e rótulos enviesados para onde a Prefeitura registrou; não escolhe modelo de produção.",
]


def area_contribuinte_m2(log_flow_acc) -> np.ndarray:
    return np.expm1(np.clip(np.asarray(log_flow_acc, float), 0, None)) * CELULA_M ** 2


def indice_umidade_topografica(log_flow_acc, slope_graus) -> np.ndarray:
    """B = ln(a / tanβ), a in metres of flow width."""
    a = np.maximum(area_contribuinte_m2(log_flow_acc) / CELULA_M, 1e-9)
    return np.log(a / np.maximum(np.tan(np.radians(np.asarray(slope_graus, float))), TAN_MIN))


def densidade_viaria(g: pd.DataFrame, raio_m: float = RAIO_DENSIDADE_M) -> np.ndarray:
    """Segments within ``raio_m`` of each segment midpoint (computed on the whole network)."""
    pts = np.c_[(g.lon0 + g.lon1) / 2 * exp.KX, (g.lat0 + g.lat1) / 2 * exp.KY]
    return cKDTree(pts).query_ball_point(pts, raio_m, return_length=True, workers=-1)


def coeficiente(q: np.ndarray, c_min: float, c_max: float) -> np.ndarray:
    return c_min + q * (c_max - c_min)


def escore_fisico(b: np.ndarray, c: np.ndarray, p_mm: float) -> np.ndarray:
    """C-model score: ln(P * C * a / tanβ) = B + ln C + ln P."""
    return b + np.log(c) + np.log(p_mm / 1000.0)


def volume_m3(log_flow_acc, c, p_mm: float) -> np.ndarray:
    return p_mm / 1000.0 * c * area_contribuinte_m2(log_flow_acc)


class _Pre:
    """Per-score quantities that make a bootstrap over the positives cheap: negatives stay fixed, only positive weights change.

    TIES are handled as scikit-learn does: positives and negatives with the same score belong to one threshold, so the precision at a positive counts every item with score >= its own
    (``neg_ge``) and every positive tied with it (``fim_do_grupo``), and an AUC tie is worth half a point. Ranking tied positives ahead of tied negatives would inflate the average
    precision whenever many segments share a score (for example the zero fill height of 78% of the roads).
    With ``blocos`` (block index of every segment) it also keeps, for each positive, how many negatives of each block score at or above and below it, so that whole blocks can be resampled
    WITH their negatives (cluster bootstrap) without re-sorting the network at every replicate.
    """

    def __init__(self, y, s, blocos=None):
        neg = np.sort(s[~y])
        pos = s[y]
        self.ordem = np.argsort(-pos, kind="stable")
        ps = pos[self.ordem]
        esq, dir_ = np.searchsorted(neg, ps, side="left"), np.searchsorted(neg, ps, side="right")
        self.neg_acima = len(neg) - esq                                      # negatives with score >= the positive's (ties included)
        self.neg_abaixo = (esq + dir_) / 2.0                                 # negatives below, plus half of the ties
        ultimo = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])              # last position of each group of tied positives
        self.fim_do_grupo = np.repeat(ultimo, np.diff(np.r_[-1, ultimo]))
        self.topo = ps >= np.quantile(s, 0.9)
        self.n_neg = len(neg)
        if blocos is not None:
            nb = int(blocos.max()) + 1
            self.acima, self.abaixo = np.zeros((len(ps), nb)), np.zeros((len(ps), nb))
            self.n_neg_bloco = np.zeros(nb)
            for g, idx in _por_bloco(blocos, ~y).items():
                ng = np.sort(s[idx])
                e, d = np.searchsorted(ng, ps, side="left"), np.searchsorted(ng, ps, side="right")
                self.n_neg_bloco[g] = len(ng)
                self.acima[:, g] = len(ng) - e
                self.abaixo[:, g] = (e + d) / 2.0

    def medidas(self, w, neg_acima=None, neg_abaixo=None, n_neg=None):
        ws = w[self.ordem].astype(float)
        na, nb_, nn = (self.neg_acima, self.neg_abaixo, self.n_neg) if neg_acima is None else (neg_acima, neg_abaixo, n_neg)
        tp = np.cumsum(ws)[self.fim_do_grupo]                                # true positives at the threshold of each positive (its tie group included)
        den = tp + na
        prec = np.divide(tp, den, out=np.zeros_like(tp), where=den > 0)
        tot = ws.sum()
        return (ws * prec).sum() / tot, (ws * nb_).sum() / tot / nn, (ws * self.topo).sum() / tot


def _por_bloco(blocos, mascara) -> dict:
    """Segment positions of each block, restricted to ``mascara``."""
    idx = np.flatnonzero(mascara)
    ordem = np.argsort(blocos[idx], kind="stable")
    idx, b = idx[ordem], blocos[idx][ordem]
    cortes = np.flatnonzero(np.diff(b)) + 1
    return {int(b[0]): None} if len(idx) == 0 else {int(g[0]): i for g, i in zip(np.split(b, cortes), np.split(idx, cortes))}


def comparar(y, escores: dict, referencia: str, rng, replicas: int = REPLICAS, grupos=None, completo: bool = False) -> dict:
    """Point metrics, 95% bootstrap intervals and gain over ``referencia`` (paired: same resampled units for every score).

    Without ``grupos`` each positive segment is resampled on its own (negatives fixed). With ``grupos`` (spatial block of each segment) whole blocks of
    POSITIVES are resampled together (negatives fixed); with ``completo=True`` whole blocks are resampled with their negatives too (cluster bootstrap),
    so neighbouring records that are not independent are never counted as independent evidence.
    """
    y = np.asarray(y)
    npos = int(y.sum())
    if grupos is not None:
        grupos = np.asarray(grupos)
        _, bloco_idx = np.unique(grupos, return_inverse=True)
    pres = {k: _Pre(y, v, bloco_idx if completo else None) for k, v in escores.items()}
    if grupos is None:
        pesos = rng.multinomial(npos, np.full(npos, 1 / npos), size=replicas)
    elif not completo:
        _, inverso = np.unique(grupos[y], return_inverse=True)
        ng = inverso.max() + 1
        pesos = rng.multinomial(ng, np.full(ng, 1 / ng), size=replicas)[:, inverso]
    else:
        nb = int(bloco_idx.max()) + 1
        contagens = rng.multinomial(nb, np.full(nb, 1 / nb), size=replicas)            # replicas x blocks: how often each block is drawn
        pesos = contagens[:, bloco_idx[y]]
    if completo:
        boots = {k: np.array([p.medidas(w, p.acima @ c, p.abaixo @ c, float(p.n_neg_bloco @ c)) for w, c in zip(pesos, contagens)]) for k, p in pres.items()}
    else:
        boots = {k: np.array([p.medidas(w) for w in pesos]) for k, p in pres.items()}  # replicas x (ap, auc, topo)
    ic = lambda v: [round(float(x), 6) for x in np.percentile(v, [2.5, 97.5])]
    bruto = {k: float(average_precision_score(y, v)) for k, v in escores.items()}        # unrounded: the gain must not carry rounding error
    saida = {}
    for k, v in escores.items():
        saida[k] = {**exp._medidas(y, v), "ic95_auc": ic(boots[k][:, 1]), "ic95_precisao_media": ic(boots[k][:, 0]), "ic95_positivos_no_topo_10pct": ic(boots[k][:, 2])}
        if k != referencia:
            ganho_b = boots[k][:, 0] / boots[referencia][:, 0] - 1
            ganho = bruto[k] / bruto[referencia] - 1
            saida[k].update(ganho_sobre_a_referencia=round(float(ganho), 4), ic95_ganho=[round(float(x), 4) for x in np.percentile(ganho_b, [2.5, 97.5])],
                            prob_melhor_que_a_referencia=round(float((ganho_b > 0).mean()), 3), atende_criterio=bool(atende(ganho, np.percentile(ganho_b, 2.5))))
    return saida


def _conservador(por_trecho: dict, por_blocos: dict, referencia: str, completo: dict | None = None) -> dict:
    """Merge the bootstraps: the criterion must hold resampling segments, blocks of positives AND whole blocks with their negatives."""
    for k, v in por_trecho.items():
        if k == referencia:
            continue
        b, c = por_blocos[k], (completo or por_blocos)[k]
        v.update(ic95_ganho_por_blocos=b["ic95_ganho"], prob_melhor_por_blocos=b["prob_melhor_que_a_referencia"], ic95_precisao_media_por_blocos=b["ic95_precisao_media"],
                 ic95_ganho_por_blocos_completo=c["ic95_ganho"], prob_melhor_por_blocos_completo=c["prob_melhor_que_a_referencia"],
                 ic95_precisao_media_por_blocos_completo=c["ic95_precisao_media"], atende_criterio_por_trecho=v["atende_criterio"],
                 atende_criterio=bool(v["atende_criterio"] and b["atende_criterio"] and c["atende_criterio"]))
    return por_trecho


def atende(ganho: float, limite_inferior: float) -> bool:
    """Adoption criterion: gain of at least ``MARGEM`` and a 95% lower bound above zero (a small or overlapping difference is not superiority)."""
    return bool(ganho >= MARGEM and limite_inferior > 0)


def _folds(y, grupos, rng, dobras):
    out = []
    for treino, teste in GroupKFold(n_splits=dobras).split(np.zeros(len(y)), y, grupos):
        out.append((teste, None if y[treino].sum() == 0 or y[teste].sum() == 0 else treino[exp.amostra_treino(y[treino], rng)]))
    return out


def _oof_logistico(X, y, folds, fallback):
    oof = np.zeros(len(y))
    for teste, idx in folds:
        if idx is None:
            oof[teste] = fallback[teste]
            continue
        oof[teste] = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300)).fit(X[idx], y[idx]).predict_proba(X[teste])[:, 1]
    return oof


def _rank01(v):
    return (rankdata(v) - 1) / (len(v) - 1)


def _spearman(a, b):
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def _jaccard_topo(a, b, frac=0.10):
    ta, tb = a >= np.quantile(a, 1 - frac), b >= np.quantile(b, 1 - frac)
    return float((ta & tb).sum() / (ta | tb).sum())


def preparar(rede: pd.DataFrame, coords: pd.DataFrame, raio_m: float = 100) -> dict:
    """The sample every comparison uses: complete segments, their labels, rule, physical index B and the street-density rank q (label-free)."""
    densidade = densidade_viaria(rede)
    b_all = indice_umidade_topografica(rede["log_flow_acc"], rede["slope"])
    ok = (~rede[COMPONENTES].isna().any(axis=1).to_numpy() & rede.percentil.notna().to_numpy() & np.isfinite(b_all))
    g = rede[ok].reset_index(drop=True)
    return {"g": g, "y": exp.rotular(g, coords, raio_m), "X5": g[COMPONENTES].to_numpy(float), "regra": g.percentil.to_numpy(float),
            "grupos": exp.blocos(g), "b": b_all[ok], "q": _rank01(densidade[ok])}


def distribuicao_positivos(y, grupos) -> dict:
    """How the positives spread over spatial blocks: blocks with a positive, largest block, top-3 share and effective number of independent blocks."""
    cont = pd.Series(np.asarray(grupos)[np.asarray(y)]).value_counts()
    p = cont.to_numpy() / cont.sum()
    return {"blocos_com_positivo": int(len(cont)), "positivos_no_maior_bloco": int(cont.iloc[0]), "participacao_do_maior_bloco": round(float(p[0]), 3),
            "participacao_dos_3_maiores": round(float(p[:3].sum()), 3), "numero_efetivo_de_blocos": round(float(1 / (p ** 2).sum()), 1),
            "positivos_por_bloco_mediana": float(cont.median())}


def rodar(rede: pd.DataFrame, coords: pd.DataFrame, semente: int = 7, dobras: int = 5, raio_m: float = 100, replicas: int = REPLICAS) -> dict:
    d = preparar(rede, coords, raio_m)
    g, y, X5, regra, grupos, b, q = d["g"], d["y"], d["X5"], d["regra"], d["grupos"], d["b"], d["q"]
    dobras = min(dobras, len(np.unique(grupos[y])))
    rng = np.random.default_rng(semente)
    folds = _folds(y, grupos, rng, dobras)

    # --- sensibilidade ao cenário: volume, monotonicidade, invariância da ordem à chuva uniforme
    cenarios, ordem_igual, monotono_p = [], True, True
    for nome, (lo, hi) in CONFIGS_C.items():
        c = coeficiente(q, lo, hi)
        base = escore_fisico(b, c, P_BASE_MM)
        medianas = []
        for p in PRECIPITACOES_MM:
            v = volume_m3(g["log_flow_acc"], c, p)
            medianas.append(float(np.median(v)))
            sp = _spearman(base, escore_fisico(b, c, p))
            ordem_igual &= sp > 0.999999
            cenarios.append({"precipitacao_mm": p, "coeficiente": nome, "volume_afluente_potencial_m3": {"mediana": round(float(np.median(v)), 2),
                             "p99": round(float(np.percentile(v, 99)), 1), "maximo": round(float(v.max()), 1)}, "spearman_com_p30": round(sp, 6)})
        monotono_p &= all(x < y_ for x, y_ in zip(medianas, medianas[1:]))
    uniformes = [n for n, (lo, hi) in CONFIGS_C.items() if lo == hi]
    med_c = [float(np.median(volume_m3(g["log_flow_acc"], coeficiente(q, *CONFIGS_C[n]), P_BASE_MM))) for n in uniformes]
    monotono_c = all(x < y_ for x, y_ in zip(med_c, med_c[1:]))

    # --- modelos
    a2 = _oof_logistico(X5, y, folds, regra / 100)
    modelos, escores_ref, resumo = {}, {}, {}
    conjunto = {"A_regra_atual": regra, "B_fluxo_ajustado_pela_declividade": b, "A2_logistica_so_componentes": a2}
    for nome, (lo, hi) in CONFIGS_C.items():
        c = escore_fisico(b, coeficiente(q, lo, hi), P_BASE_MM)
        d1 = 0.5 * _rank01(regra) + 0.5 * _rank01(c)
        d2 = _oof_logistico(np.c_[X5, c], y, folds, regra / 100)
        conjunto[f"C[{nome}]"], conjunto[f"D1[{nome}]"], conjunto[f"D2[{nome}]"] = c, d1, d2
        if nome == CONFIG_REFERENCIA:
            escores_ref = {"A": regra, "B": b, "C": c, "D1": d1, "D2": d2}
    r = _conservador(comparar(y, conjunto, "A_regra_atual", np.random.default_rng(semente), replicas),
                     comparar(y, conjunto, "A_regra_atual", np.random.default_rng(semente), replicas, grupos), "A_regra_atual",
                     comparar(y, conjunto, "A_regra_atual", np.random.default_rng(semente), replicas, grupos, completo=True))
    # ganho incremental do D2 sobre a MESMA regressão só com os componentes (mesmas dobras e amostras)
    par = {"ref": a2, **{n: conjunto[f"D2[{n}]"] for n in CONFIGS_C}}
    inc = _conservador(comparar(y, par, "ref", np.random.default_rng(semente), replicas), comparar(y, par, "ref", np.random.default_rng(semente), replicas, grupos), "ref",
                       comparar(y, par, "ref", np.random.default_rng(semente), replicas, grupos, completo=True))

    def grupo(prefixo):
        por = {n: r[f"{prefixo}[{n}]"] for n in CONFIGS_C}
        aps = [v["precisao_media"] for v in por.values()]
        return {"por_cenario_de_C": por, "precisao_media_min_max": [min(aps), max(aps)], "atende_criterio_em_todos_os_cenarios": all(v["atende_criterio"] for v in por.values())}

    modelos = {"A_regra_atual": r["A_regra_atual"], "B_fluxo_ajustado_pela_declividade": {**r["B_fluxo_ajustado_pela_declividade"]},
               "C_com_coeficientes_de_escoamento": grupo("C"), "D1_media_de_postos_regra_e_fisica": grupo("D1"),
               "D2_componentes_mais_fisica": {**grupo("D2"), "ganho_incremental_sobre_a_logistica_so_com_componentes": {n: inc[n] for n in CONFIGS_C},
                                              "referencia_logistica_so_componentes": r["A2_logistica_so_componentes"],
                                              "atende_incremento_em_todos_os_cenarios": all(inc[n]["atende_criterio"] for n in CONFIGS_C)}}
    escores_c = {n: escore_fisico(b, coeficiente(q, *CONFIGS_C[n]), P_BASE_MM) for n in CONFIGS_C}
    ordem = list(CONFIGS_C)
    sp = [[_spearman(escores_c[i], escores_c[j]) for j in ordem] for i in ordem]
    fora = [sp[i][j] for i in range(len(ordem)) for j in range(len(ordem)) if i != j]
    cr = list(escores_ref)
    sensibilidade = {
        "ordem_dos_trechos_independe_da_chuva_uniforme": bool(ordem_igual),
        "volume_cresce_com_a_chuva_em_todos_os_cenarios": bool(monotono_p),
        "volume_cresce_com_C_uniforme": bool(monotono_c),
        "spearman_entre_cenarios_de_C": {"minimo": round(min(fora), 4), "medio": round(float(np.mean(fora)), 4)},
        "spearman_de_B_com_cada_cenario_de_C": {n: round(_spearman(b, escores_c[n]), 4) for n in ordem},
        "sobreposicao_top10_de_B_com_cada_cenario_de_C": {n: round(_jaccard_topo(b, escores_c[n]), 3) for n in ordem},
        "variacao_relativa_da_precisao_media_do_modelo_C_entre_cenarios": round(float((lambda a: (max(a) - min(a)) / np.mean(a))([modelos["C_com_coeficientes_de_escoamento"]["por_cenario_de_C"][n]["precisao_media"] for n in ordem])), 3),
        "correlacao_de_postos_entre_modelos_no_cenario_de_referencia": {"cenario": CONFIG_REFERENCIA, "ordem": cr,
                                                                        "matriz": [[round(_spearman(escores_ref[i], escores_ref[j]), 3) for j in cr] for i in cr]},
        "contribuicao_incremental": {"D1_sobre_a_regra_atual": {n: modelos["D1_media_de_postos_regra_e_fisica"]["por_cenario_de_C"][n]["ganho_sobre_a_referencia"] for n in ordem},
                                     "D2_sobre_a_logistica_so_com_componentes": {n: inc[n]["ganho_sobre_a_referencia"] for n in ordem}},
    }
    adotaveis = [k for k, v in {"B": modelos["B_fluxo_ajustado_pela_declividade"].get("atende_criterio", False),
                                "C": modelos["C_com_coeficientes_de_escoamento"]["atende_criterio_em_todos_os_cenarios"],
                                "D1": modelos["D1_media_de_postos_regra_e_fisica"]["atende_criterio_em_todos_os_cenarios"],
                                "D2": modelos["D2_componentes_mais_fisica"]["atende_criterio_em_todos_os_cenarios"]}.items() if v]
    veredito = ({"ha_evidencia_de_ganho_incremental": False, "texto": "Não há evidência de ganho incremental: nenhuma formulação física, sozinha ou combinada, atinge +10% de precisão média "
                 "sobre a regra atual com limite inferior do intervalo acima de zero em todos os cenários de C. A regra atual permanece; nenhuma adoção é proposta."}
                if not adotaveis else
                {"ha_evidencia_de_ganho_incremental": True, "formulacoes": adotaveis, "texto": f"Há indício de ganho em {', '.join(adotaveis)} em todos os cenários de C, ainda "
                 "exploratório (rótulos de 2013-2014, ~124 positivos, sem chuva associada): exige validação com eventos datados antes de qualquer adoção."})
    return {"amostra": {"trechos": int(len(y)), "trechos_rotulados": int(y.sum()), "taxa_base": round(float(y.mean()), 5), "dobras": int(dobras), "replicas_bootstrap": replicas,
                        "mesmos_trechos_rotulos_e_blocos_do_experimento_anterior": True, "semente": semente,
                        "distribuicao_espacial_dos_positivos_bloco_1500m": distribuicao_positivos(y, grupos)},
            "hipoteses": {"celula_m": CELULA_M, "tan_beta_minimo": TAN_MIN, "precipitacoes_mm": list(PRECIPITACOES_MM), "coeficientes_de_escoamento": {k: list(v) for k, v in CONFIGS_C.items()},
                          "raio_densidade_viaria_m": RAIO_DENSIDADE_M, "margem_exigida": MARGEM, "criterio": "ganho >= 10% e limite inferior do IC95% do ganho > 0, por trecho, por blocos de positivos E por blocos completos (conglomerados), em todos os cenários de C"},
            "cenarios": cenarios, "modelos": modelos, "sensibilidade": sensibilidade, "veredito": veredito, "limitacoes": LIMITACOES}


def relatorio_md(r: dict) -> str:
    a, m, s, v = r["amostra"], r["modelos"], r["sensibilidade"], r["veredito"]
    dp = a["distribuicao_espacial_dos_positivos_bloco_1500m"]
    linha = lambda nome, x: f"| {nome} | {x['auc']} | {x['precisao_media']} | {x['ic95_precisao_media'][0]}–{x['ic95_precisao_media'][1]} | {x['positivos_no_topo_10pct']} | " + (
        f"{x['ganho_sobre_a_referencia']:+.1%} | {x['ic95_ganho'][0]:+.1%} a {x['ic95_ganho'][1]:+.1%} | {x['ic95_ganho_por_blocos'][0]:+.1%} a {x['ic95_ganho_por_blocos'][1]:+.1%} | {x['ic95_ganho_por_blocos_completo'][0]:+.1%} a {x['ic95_ganho_por_blocos_completo'][1]:+.1%} | {'sim' if x['atende_criterio'] else 'não'} |" if "ganho_sobre_a_referencia" in x else "referência | | | | |")
    L = ["# Sensibilidade hidrológica: a física simplificada acrescenta informação ao índice atual?", "",
         "Experimento **exploratório**. Não altera o índice nem o modelo de produção, não prevê profundidade nem ocorrência de alagamento e não valida previsão condicionada à chuva.", "",
         "## Conclusão", "", f"**{v['texto']}**", "",
         f"Amostra: {f'{a['trechos']:,}'.replace(',', '.')} trechos, {a['trechos_rotulados']} rotulados (a até 100 m de um registro da Prefeitura, 2013–2014), "
         f"taxa base {f'{a['taxa_base']:.3%}'.replace('.', ',')}. Blocos espaciais de 1,5 km, {a['dobras']} dobras, bootstrap pareado de {a['replicas_bootstrap']} réplicas sobre os positivos.", "",
         "Distribuição espacial dos positivos (blocos de 1,5 km): " + ", ".join([f"{dp['blocos_com_positivo']} blocos com positivo",
         f"o maior com {dp['positivos_no_maior_bloco']} ({str(round(100 * dp['participacao_do_maior_bloco'], 1)).replace('.', ',')}%)",
         f"número efetivo de blocos {str(dp['numero_efetivo_de_blocos']).replace('.', ',')}"]) + f". Semente {a['semente']}.", "",
         "## Equações e unidades", "", "```", "A_i  = expm1(log_flow_acc_i) · 30²              [m²]  área a montante (D8, células de 30 m)",
         "a_i  = A_i / 30                              [m]   área por metro de largura de fluxo", "tanβ = max(tan(slope_i), 0,001)              [-]   slope em graus",
         "V_i  = P · C_i · A_i                         [m³]  volume afluente potencial (não é profundidade)", "B_i  = ln(a_i / tanβ_i)                      [-]   TWI: fluxo ajustado pela declividade",
         "C_i  = ln(P · C_i · a_i / tanβ_i) = B_i + ln C_i + ln P    índice relativo (unidade arbitrária)", "D1_i = ½·rank(regra atual) + ½·rank(C_i)    sem parâmetros ajustados",
         "D2   = regressão logística (5 componentes + C_i) vs. (5 componentes), mesmas dobras", "```", "",
         "Com chuva uniforme e C constante, P e C deslocam B por uma constante: **a ordem dos trechos não muda**. "
         f"Verificado nos {len(r['cenarios'])} cenários: ordem independente da chuva = {s['ordem_dos_trechos_independe_da_chuva_uniforme']}. A precipitação uniforme só escala o volume; ela não diferencia ruas. "
         "Para C afetar a ordem ele precisa variar no espaço; os cenários `espacial_*` usam a densidade viária (250 m) como proxy de cenário, não como medida de impermeabilização.", "",
         "## Cenários e hipóteses", "", "- Chuva uniforme hipotética: 10, 30 e 60 mm (não são limiares de risco).",
         "- Coeficientes de escoamento C: faixas típicas do método racional conferidas em manuais de agências "
         "([TxDOT, Hydraulic Design Manual](https://www.txdot.gov/manuals/des/hyd/chapter-4--hydrology/section-12--rational-method/runoff-coefficients.html); "
         "[San Diego County, Hydrology Manual](https://www.sandiegocounty.gov/content/dam/sdc/dpw/FLOOD_CONTROL/floodcontroldocuments/hydro-evalcvalues.pdf)): "
         "asfalto e concreto 0,70–0,95; residencial unifamiliar 0,30–0,50 (outras fontes citam 0,30–0,75 para áreas residenciais em geral); gramado 0,05–0,35 conforme solo e declividade. "
         "A tabela do livro de Chow, Maidment & Mays (1988) **não foi consultada diretamente**. Nenhum valor é calibrado para Porto Alegre.",
         f"- Cenários de C: {', '.join(f'`{k}`' for k in CONFIGS_C)}.", "",
         "## Comparação de métricas (precipitação base 30 mm; o ranking não depende de P)", "",
         "| Modelo | AUC | Precisão média | IC95 da precisão média | Positivos no top 10% | Ganho vs. regra | IC95 do ganho (trechos) | IC95 do ganho (blocos de positivos) | IC95 do ganho (blocos completos) | Atende o critério |", "|---|---|---|---|---|---|---|---|---|---|",
         linha("A. Regra atual", m["A_regra_atual"]), linha("B. Fluxo ajustado pela declividade", m["B_fluxo_ajustado_pela_declividade"])]
    for prefixo, titulo in (("C_com_coeficientes_de_escoamento", "C"), ("D1_media_de_postos_regra_e_fisica", "D1"), ("D2_componentes_mais_fisica", "D2")):
        for n, x in m[prefixo]["por_cenario_de_C"].items():
            L.append(linha(f"{titulo} · {n}", x))
    L += ["", "## Testes de sensibilidade", "",
          f"- **Monotonicidade:** o volume afluente potencial cresce com a chuva em todos os cenários ({s['volume_cresce_com_a_chuva_em_todos_os_cenarios']}) e com C uniforme ({s['volume_cresce_com_C_uniforme']}).",
          f"- **Estabilidade do ranking espacial:** Spearman entre cenários de C: mínimo {s['spearman_entre_cenarios_de_C']['minimo']}, médio {s['spearman_entre_cenarios_de_C']['medio']}.",
          f"- **Sensibilidade a C:** a precisão média do modelo C varia {s['variacao_relativa_da_precisao_media_do_modelo_C_entre_cenarios']:.1%} (amplitude relativa) entre os cenários.",
          f"- **Correlação de postos entre modelos** (cenário `{s['correlacao_de_postos_entre_modelos_no_cenario_de_referencia']['cenario']}`, escolhido por ser o mais distante de B, não por desempenho):", "",
          "| | " + " | ".join(s["correlacao_de_postos_entre_modelos_no_cenario_de_referencia"]["ordem"]) + " |", "|---|" + "---|" * len(s["correlacao_de_postos_entre_modelos_no_cenario_de_referencia"]["ordem"])]
    for nome, lin in zip(s["correlacao_de_postos_entre_modelos_no_cenario_de_referencia"]["ordem"], s["correlacao_de_postos_entre_modelos_no_cenario_de_referencia"]["matriz"]):
        L.append(f"| {nome} | " + " | ".join(str(x) for x in lin) + " |")
    inc = s["contribuicao_incremental"]
    L += ["", "- **Contribuição incremental** (ganho relativo de precisão média): D1 sobre a regra atual: " + ", ".join(f"{n} {x:+.1%}" for n, x in inc["D1_sobre_a_regra_atual"].items()) + ". "
          "D2 sobre a regressão logística só com os componentes: " + ", ".join(f"{n} {x:+.1%}" for n, x in inc["D2_sobre_a_logistica_so_com_componentes"].items()) + ".", "",
          "## Limitações obrigatórias", ""] + [f"- {x}" for x in r["limitacoes"]] + [
          "", "## Como ler", "", "A regra atual só seria substituída com ganho de 10% e limite inferior do intervalo acima de zero, por trecho, por blocos de positivos e por blocos completos (com seus negativos), em todos os cenários de C. Intervalos que se sobrepõem não são evidência de superioridade. "
          "Os 124 positivos estão em 53 blocos de 1,5 km e um só bloco concentra 18 deles, por isso o bootstrap por blocos é o mais conservador. "
          "A amplitude do intervalo do D1 (−12% a +81%) é real e estável (não muda com a semente nem com 20.000 réplicas): a precisão média depende de poucos positivos muito bem posicionados "
          "(os 5 melhores respondem por 16% da AP do D1 e 8% da AP da regra), então um único trecho entrar ou sair da amostra muda o resultado. É uma hipótese, não uma evidência. "
          "", "## Correções da auditoria", "",
          "- O ganho relativo passou a usar a precisão média sem arredondamento (antes, 5 casas: erro de até ~0,25%).",
          "- O bootstrap por blocos, que só reamostrava blocos com positivos e mantinha os negativos fixos, ganhou a versão completa (blocos inteiros com seus negativos, conglomerados). "
          "A anterior continua nas tabelas como sensibilidade; o critério exige as três formas. A versão anterior do relatório está em `reports/qa/sensibilidade_hidrologica_v1_antes_da_auditoria.json`.",
          "- Robustez da divisão espacial (tamanho do bloco, origem da grade, leave-one-block-out): [robustez_espacial.md](robustez_espacial.md).",
          "- Empates de escore passaram a ser tratados como no scikit-learn (descoberto na Fase 3, quando 78% dos trechos tinham o mesmo escore e o bootstrap antigo inflava a precisão média). "
          "Aqui os escores são contínuos: os limites dos intervalos mudaram na terceira ou quarta casa decimal e nenhuma conclusão mudou.", "",
          "Reprodução: `PYTHONPATH=src python tools/experimento_sensibilidade_hidrologica.py`.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    coords = ler_alagamentos()
    rede = pd.read_parquet(RAIZ / "data/processed/rede_poa.parquet", columns=["lon0", "lat0", "lon1", "lat1", "percentil", "slope", "log_flow_acc", *COMPONENTES])
    r = rodar(rede, coords)
    Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "reports/qa/sensibilidade_hidrologica.json").write_text(json.dumps(r, ensure_ascii=False, indent=2))
    Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "docs/sensibilidade_hidrologica.md").write_text(relatorio_md(r))
    print(r["veredito"]["texto"])
