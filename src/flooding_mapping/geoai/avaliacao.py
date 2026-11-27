"""Métricas da validação espacial: erro das frações, classes duras, estratos, bairros, estabilidade entre blocos, incerteza e bootstrap por blocos."""

from __future__ import annotations

import numpy as np

from .referencia import GRUPOS

CONSTRUIDO = GRUPOS.index("construido")


def erros_da_fracao(ref: np.ndarray, pred: np.ndarray) -> dict:
    e = pred - ref
    return {"mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())), "vies": float(e.mean()), "n": int(len(e))}


def matriz_de_confusao(ref_cls: np.ndarray, pred_cls: np.ndarray, n: int = len(GRUPOS)) -> np.ndarray:
    """Linhas = referência, colunas = previsão."""
    return np.bincount(ref_cls * n + pred_cls, minlength=n * n).reshape(n, n)


def f1_e_iou(cm: np.ndarray) -> dict:
    tp = np.diag(cm).astype(float)
    precisao = np.divide(tp, cm.sum(0), out=np.full(len(tp), np.nan), where=cm.sum(0) > 0)
    recall = np.divide(tp, cm.sum(1), out=np.full(len(tp), np.nan), where=cm.sum(1) > 0)
    f1 = np.divide(2 * precisao * recall, precisao + recall, out=np.full(len(tp), np.nan), where=(precisao + recall) > 0)
    f1 = np.where((cm.sum(1) > 0) & ~np.isfinite(f1), 0.0, f1)        # classe que existe na referência e nunca foi acertada (ou prevista) vale 0, não "indefinido"
    iou = np.divide(tp, cm.sum(0) + cm.sum(1) - tp, out=np.full(len(tp), np.nan), where=(cm.sum(0) + cm.sum(1) - tp) > 0)
    return {"precisao": precisao.tolist(), "recall": recall.tolist(), "f1": f1.tolist(), "iou": iou.tolist(), "macro_f1": float(np.nanmean(f1)), "suporte": cm.sum(1).tolist()}


def estatisticas_por_bloco(ref: np.ndarray, pred: np.ndarray, bloco: np.ndarray) -> dict:
    """Somas por bloco suficientes para recalcular MAE, RMSE, viés e a matriz de confusão em qualquer reamostragem de blocos."""
    ids, inv = np.unique(bloco, return_inverse=True)
    e = pred[:, CONSTRUIDO] - ref[:, CONSTRUIDO]
    cm = np.zeros((len(ids), len(GRUPOS), len(GRUPOS)))
    np.add.at(cm, (inv, ref.argmax(1), pred.argmax(1)), 1)
    return {"ids": ids, "n": np.bincount(inv).astype(float), "abs": np.bincount(inv, np.abs(e)), "sq": np.bincount(inv, e ** 2), "e": np.bincount(inv, e), "cm": cm}


def _resumir(ev: dict, w: np.ndarray) -> dict:
    n = (ev["n"] * w).sum()
    cm = np.tensordot(w, ev["cm"], axes=1)
    f = f1_e_iou(cm)
    return {"mae": (ev["abs"] * w).sum() / n, "rmse": np.sqrt((ev["sq"] * w).sum() / n), "vies": (ev["e"] * w).sum() / n, "macro_f1": f["macro_f1"], "iou_construido": f["iou"][CONSTRUIDO], "f1_construido": f["f1"][CONSTRUIDO]}


def bootstrap_por_blocos(ev: dict, repeticoes: int, semente: int) -> dict:
    """Intervalo de 95% (percentis) reamostrando blocos inteiros: respeita a autocorrelação dentro do bloco."""
    rng = np.random.default_rng(semente)
    k = len(ev["ids"])
    amostras = [_resumir(ev, np.bincount(rng.integers(0, k, k), minlength=k).astype(float)) for _ in range(repeticoes)]
    ponto = _resumir(ev, np.ones(k))
    return {m: {"valor": float(ponto[m]), "ic95": [float(np.nanpercentile([a[m] for a in amostras], 2.5)), float(np.nanpercentile([a[m] for a in amostras], 97.5))]} for m in ponto}


def diferenca_pareada(ev_a: dict, ev_b: dict, repeticoes: int, semente: int) -> dict:
    """MAE(a) - MAE(b) com intervalo de 95% sobre os mesmos blocos reamostrados; negativo = a é melhor."""
    assert np.array_equal(ev_a["ids"], ev_b["ids"])
    rng = np.random.default_rng(semente)
    k = len(ev_a["ids"])
    d = []
    for _ in range(repeticoes):
        w = np.bincount(rng.integers(0, k, k), minlength=k).astype(float)
        d.append(_resumir(ev_a, w)["mae"] - _resumir(ev_b, w)["mae"])
    ponto = _resumir(ev_a, np.ones(k))["mae"] - _resumir(ev_b, np.ones(k))["mae"]
    return {"diferenca_mae": float(ponto), "ic95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}


def por_estrato(ref: np.ndarray, pred: np.ndarray, valores: np.ndarray, limites: list[float]) -> list[dict]:
    out = []
    for lo, hi in zip(limites[:-1], limites[1:]):
        m = (valores >= lo) & (valores < hi)
        if m.sum():
            out.append({"de": lo, "ate": min(hi, 1.0), **erros_da_fracao(ref[m][:, CONSTRUIDO], pred[m][:, CONSTRUIDO])})
    return out


def erro_de_area_por_bairro(ref: np.ndarray, pred: np.ndarray, area_nao_mista_m2: np.ndarray, bairro: np.ndarray, nomes: list[str], limite: float, minimo_de_celulas: int = 200) -> dict:
    linhas = []
    for i, nome in enumerate(nomes):
        m = bairro == i
        if m.sum() < minimo_de_celulas:
            continue
        a_ref = float((ref[m, CONSTRUIDO] * area_nao_mista_m2[m]).sum())
        a_pred = float((pred[m, CONSTRUIDO] * area_nao_mista_m2[m]).sum())
        if a_ref > 0:
            linhas.append({"bairro": nome, "celulas": int(m.sum()), "area_construida_ref_km2": a_ref / 1e6, "area_construida_prevista_km2": a_pred / 1e6, "erro_relativo": (a_pred - a_ref) / a_ref})
    er = np.array([abs(l["erro_relativo"]) for l in linhas])
    return {"bairros_avaliados": len(linhas), "fracao_dentro_do_limite": float((er <= limite).mean()) if len(er) else None, "erro_relativo_mediano_abs": float(np.median(er)) if len(er) else None,
            "erro_relativo_total": float((sum(l["area_construida_prevista_km2"] for l in linhas) - sum(l["area_construida_ref_km2"] for l in linhas)) / sum(l["area_construida_ref_km2"] for l in linhas)) if linhas else None,
            "bairros": sorted(linhas, key=lambda l: -abs(l["erro_relativo"]))}


def estabilidade_entre_blocos(ev: dict, limite_mae: float) -> dict:
    mae = ev["abs"] / ev["n"]
    return {"blocos": int(len(mae)), "mae_mediano": float(np.median(mae)), "mae_p10_p90": [float(np.percentile(mae, 10)), float(np.percentile(mae, 90))], "mae_pior": float(mae.max()),
            "fracao_de_blocos_dentro_do_limite": float((mae <= limite_mae).mean())}


def incerteza(desvio: np.ndarray, erro_abs: np.ndarray, residuos_de_calibracao: np.ndarray, alpha: float = 0.10) -> dict:
    """Relação entre o desvio das árvores e o erro, e cobertura de um intervalo conforme calculado com resíduos de outras dobras."""
    from scipy.stats import spearmanr
    q = float(np.quantile(residuos_de_calibracao, 1 - alpha))
    decis = np.quantile(desvio, np.linspace(0, 1, 6))
    faixas = [{"desvio_de": float(a), "desvio_ate": float(b), "erro_abs_medio": float(erro_abs[(desvio >= a) & (desvio <= b)].mean())} for a, b in zip(decis[:-1], decis[1:])]
    return {"spearman_desvio_x_erro": float(spearmanr(desvio, erro_abs)[0]), "meio_intervalo_conforme_90": q, "cobertura_observada": float((erro_abs <= q).mean()), "erro_por_quintil_de_desvio": faixas}
