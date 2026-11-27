"""Gera docs/geoai_resultados.md a partir de reports/qa/geoai_resultados.json e do manifesto do experimento (nenhum número é digitado à mão).

    PYTHONPATH=src .venv/bin/python tools/gerar_relatorio_geoai.py
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CLASSES = ["construído", "vegetação", "solo exposto", "água"]


def n(x: float, c: int = 3) -> str:
    return f"{x:.{c}f}".replace(".", ",")


def mil(x: float) -> str:
    return f"{int(x):,}".replace(",", ".")


def ic(d: dict, c: int = 3) -> str:
    return f"{n(d['valor'], c)} [{n(d['ic95'][0], c)}; {n(d['ic95'][1], c)}]"


def figura_dos_mapas(man: dict, cfg_rotulos: dict) -> None:
    """Três mapas lado a lado, só nas células avaliadas (previstas fora da dobra): Profill, estimativa e erro. Lê o COG e a Profill; não treina nada."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from flooding_mapping.geoai import referencia as rf
    q = json.loads((RAIZ / "data/processed/uso_solo/qualidade_uso_solo.json").read_text())
    alvos = rf.alvos_da_profill(RAIZ / "data/processed/uso_solo/uso_solo_grade30m.parquet", RAIZ / "data/processed/uso_solo/classes_e_codigos.json", q["grade"], cfg_rotulos)
    with rasterio.open(RAIZ / man["produto"]["arquivo"]) as s:
        est, origem = s.read(1), s.read(7)
    avaliada = origem == 1
    ref = np.where(avaliada, alvos["frac_construido"], np.nan)
    previsto = np.where(avaliada, est, np.nan)
    fig, ax = plt.subplots(1, 3, figsize=(14, 5.4))
    for a, (m, tit, cmap, lim) in zip(ax, [(ref, "Profill: fração construída", "magma_r", (0, 1)), (previsto, "Estimada pelo Random Forest (fora da dobra)", "magma_r", (0, 1)), (previsto - ref, "Erro (estimada − Profill)", "RdBu_r", (-0.5, 0.5))]):
        im = a.imshow(m, cmap=cmap, vmin=lim[0], vmax=lim[1])
        a.set_title(tit, fontsize=9)
        a.axis("off")
        fig.colorbar(im, ax=a, fraction=0.04)
    fig.suptitle("Só as células com rótulo utilizável da Profill; fora delas o produto é extrapolação sem validação (banda origem_da_previsao = 2)", fontsize=8)
    fig.tight_layout()
    (RAIZ / "data/interim/geoai/figuras_locais").mkdir(parents=True, exist_ok=True)   # deriva da Profill: fora do Git e da publicação
    fig.savefig(RAIZ / "data/interim/geoai/figuras_locais/geoai_mapas_fracao_construida.png", dpi=130)
    plt.close(fig)


def main() -> None:
    r = json.loads((RAIZ / "reports/qa/geoai_resultados.json").read_text())
    exp = r["meta"]["experimento"]
    man = json.loads((RAIZ / f"data/processed/geoai/manifesto_{exp}.json").read_text())
    lim = r["meta"]["limiares_operacionais"]
    p1, p2, prim = r["P1_blocos"], r["P2_quadrantes"], r["primario"]
    nome_prim = prim["modelo"]
    from flooding_mapping import config as cfgmod
    figura_dos_mapas(man, cfgmod.load_config(RAIZ / "config/geoai.yaml")["rotulos"])
    L = [f"# Resultados do experimento GeoAI (Fase 5)", "",
         f"Relatório **gerado** por `tools/gerar_relatorio_geoai.py` a partir de `reports/qa/geoai_resultados.json` e do manifesto `data/processed/geoai/manifesto_{exp}.json` (ambos fora do Git). Interpretação, limites e decisão: [`geoai_fase5.md`](geoai_fase5.md).", "",
         f"- **Experimento:** `{exp}`, executado em {man['executado_em'][:10]}; {r['meta']['celulas_no_experimento']:,} células de 30 m ".replace(",", ".") +
         f"({r['meta']['blocos']['blocos_usados']} blocos de 3 km em {len(r['meta']['blocos']['celulas_por_dobra'])} dobras; {len(r['meta']['blocos']['blocos_excluidos_por_poucas_celulas'])} blocos de borda excluídos por terem poucas células).",
         f"- **Imagens:** Sentinel-2 L2A, tile {man['imagens']['tile']}, {len(man['imagens']['cenas'])} cenas de {man['imagens']['periodo'][0]} a {man['imagens']['periodo'][1]}, linha(s) de processamento {', '.join(man['imagens']['linhas_de_processamento'])}; mediana por pixel após máscara SCL.",
         "- **Referência:** Profill 2022 (interpretação visual de ortoimagem de 30 cm, 2018 a 2021). Ela é o rótulo de treino **e** a referência de avaliação: os números abaixo medem a **concordância com a Profill em blocos não vistos**, não a exatidão contra a verdade de campo.",
         "- **Alvo:** fração da célula em cada grupo, sobre a área que a Profill classifica fora da classe mista \"Jardins, Passeios ou Áreas semi urbanizadas\". Construído = Edificação + Vias Pavimentadas.",
         "- Intervalos entre colchetes: 95% por reamostragem de **blocos** (bootstrap), não de células.", ""]
    L += ["## 1. Protocolo P1: validação espacial por blocos (5 dobras, buffer de 5 células)", "",
          "| Modelo | MAE fração construída | RMSE | Viés | Macro F1 | IoU construído | F1 construído |", "|---|---|---|---|---|---|---|"]
    for nome, v in p1.items():
        b = v["bootstrap_por_blocos"]
        L.append(f"| `{nome}` | {ic(b['mae'])} | {ic(b['rmse'])} | {ic(b['vies'])} | {ic(b['macro_f1'])} | {ic(b['iou_construido'])} | {ic(b['f1_construido'])} |")
    L += ["", "`media_do_treino` e `linear_ndvi_ndbi_mndwi` são controles ingênuos. `rf_S1` a `rf_S4` são o Random Forest com conjuntos crescentes de atributos; `rf_AEF` e `linear_AEF` usam os embeddings AlphaEarth de 2020 (64 dimensões) com o mesmo protocolo.", "",
          "### Escolha do conjunto de atributos do Random Forest", "", f"Regra fixada antes de rodar: partir de S1 e só adotar o conjunto seguinte se o intervalo de 95% (blocos) da redução de MAE exclui zero. **Escolhido: `{nome_prim}`.**", "",
          "| De | Para | MAE(anterior) − MAE(seguinte) | IC 95% | Adotado |", "|---|---|---|---|---|"]
    for p in r["escolha_do_conjunto_de_atributos"]["passos"]:
        L.append(f"| {p['de']} | {p['para']} | {n(p['diferenca_mae'], 4)} | [{n(p['ic95'][0], 4)}; {n(p['ic95'][1], 4)}] | {'sim' if p['adotado'] else 'não'} |")
    L += ["", f"### Comparação pareada com o modelo primário (`{nome_prim}`)", "", "Diferença de MAE (modelo − primário) nos mesmos blocos reamostrados; negativa = o modelo é melhor que o primário; intervalo que contém zero = sem diferença demonstrada.", "",
          "| Modelo | Diferença de MAE | IC 95% | Leitura |", "|---|---|---|---|"]
    for nome, d in r["comparacao_pareada_com_o_primario"].items():
        leitura = "melhor que o primário" if d["ic95"][1] < 0 else "pior que o primário" if d["ic95"][0] > 0 else "sem diferença demonstrada"
        L.append(f"| `{nome}` | {n(d['diferenca_mae'], 4)} | [{n(d['ic95'][0], 4)}; {n(d['ic95'][1], 4)}] | {leitura} |")
    L += ["", "## 2. Protocolo P2: deixar um quadrante inteiro de fora", "", "Quatro quadrantes (norte/sul × oeste/leste); cada um é previsto por um modelo treinado nos outros três, com buffer. É o teste mais próximo de \"aplicar onde o modelo não viu nada parecido\".", "",
          "| Modelo | MAE fração construída | Viés | Macro F1 | MAE por quadrante (0 a 3) |", "|---|---|---|---|---|"]
    for nome, v in p2.items():
        b = v["bootstrap_por_blocos"]
        L.append(f"| `{nome}` | {ic(b['mae'])} | {ic(b['vies'])} | {ic(b['macro_f1'])} | " + "; ".join(f"{k}: {n(q['mae'])}" for k, q in v["por_quadrante"].items()) + " |")
    L += ["", f"## 3. Classes duras do modelo primário (`{nome_prim}`, P1)", "", "Classe dura = maior fração. Linhas = Profill, colunas = estimativa.", "", "| | " + " | ".join(CLASSES) + " | Suporte | Precisão | Recall | F1 | IoU |", "|---|" + "---|" * (len(CLASSES) + 5)]
    cm, cd = prim["matriz_de_confusao_ref_x_prev"], prim["classes_duras"]
    for i, c in enumerate(CLASSES):
        L.append(f"| **{c}** | " + " | ".join(mil(x) for x in cm[i]) + f" | {mil(cd['suporte'][i])} | {n(cd['precisao'][i])} | {n(cd['recall'][i])} | {n(cd['f1'][i])} | {n(cd['iou'][i])} |")
    L += ["", f"Macro F1: {n(cd['macro_f1'])}. Água e solo exposto têm poucas células e, a 10 m, se confundem com o construído e entre si: os números dessas duas classes têm pouco peso e não sustentam uso.", "",
          "## 4. Onde o modelo erra: estrato de classe mista", "", "Fração da célula em \"Jardins, Passeios ou Áreas semi urbanizadas\", que a Profill não permite tratar como construída nem como permeável.", "", "| Fração mista | Células | MAE | Viés |", "|---|---|---|---|"]
    for e in prim["por_estrato_de_jardins"]:
        L.append(f"| {n(e['de'], 2)} a {n(e['ate'], 2)} | {mil(e['n'])} | {n(e['mae'])} | {n(e['vies'], 3)} |")
    est = prim["estabilidade_entre_blocos"]
    L += ["", "## 5. Estabilidade entre blocos", "", f"{est['blocos']} blocos de 3 km: MAE mediano {n(est['mae_mediano'])}; percentis 10 e 90: {n(est['mae_p10_p90'][0])} e {n(est['mae_p10_p90'][1])}; pior bloco {n(est['mae_pior'])}. "
          f"**{n(100 * est['fracao_de_blocos_dentro_do_limite'], 1)}% dos blocos** têm MAE de até {n(lim['mae_fracao_construida'], 2)}.", "", "_Figura não publicada: deriva da Profill, cuja redistribuição não foi confirmada. Ela é gerada localmente em `data/interim/geoai/figuras_locais/` (fora do Git) por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`._", ""]
    ba = prim["erro_de_area_por_bairro"]
    L += ["## 6. Erro da área construída por bairro", "", f"{ba['bairros_avaliados']} bairros com ao menos 200 células. Erro relativo total: {n(100 * ba['erro_relativo_total'], 2)}%. Erro relativo absoluto mediano: {n(100 * ba['erro_relativo_mediano_abs'], 1)}%. "
          f"**{n(100 * ba['fracao_dentro_do_limite'], 1)}% dos bairros** ficam dentro de {n(100 * lim['erro_de_area_por_bairro'], 0)}%.", "", "Os cinco maiores erros relativos:", "", "| Bairro | Células | Área construída Profill (km²) | Estimada (km²) | Erro relativo |", "|---|---|---|---|---|"]
    for b in ba["bairros"][:5]:
        L.append(f"| {b['bairro']} | {b['celulas']} | {n(b['area_construida_ref_km2'], 3)} | {n(b['area_construida_prevista_km2'], 3)} | {n(100 * b['erro_relativo'], 1)}% |")
    inc = prim["incerteza"]
    L += ["", "## 7. Incerteza", "", f"Indicador: desvio entre as 200 árvores na fração construída (incerteza do **modelo**, não intervalo de confiança). Correlação de Spearman com o erro absoluto: **{n(inc['spearman_desvio_x_erro'], 2)}**.", "",
          "| Quintil do desvio (1 = menor) | Desvio de | Desvio até | Erro absoluto médio |", "|---|---|---|---|"]
    for i, q in enumerate(inc["erro_por_quintil_de_desvio"], 1):
        L.append(f"| {i} | {n(q['desvio_de'])} | {n(q['desvio_ate'])} | {n(q['erro_abs_medio'])} |")
    cob = [c["cobertura"] for c in inc["cobertura_por_dobra"]]
    L += ["", f"Intervalo conforme de 90% (resíduos das outras dobras): cobertura observada por dobra de {n(100 * min(cob), 1)}% a {n(100 * max(cob), 1)}% (alvo: 90%). Calibração aproximada: " + inc["nota"] + ".", "", "_Figura não publicada: deriva da Profill, cuja redistribuição não foi confirmada. Ela é gerada localmente em `data/interim/geoai/figuras_locais/` (fora do Git) por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`._", "", "_Figura não publicada: deriva da Profill, cuja redistribuição não foi confirmada. Ela é gerada localmente em `data/interim/geoai/figuras_locais/` (fora do Git) por `tools/gerar_relatorio_geoai.py` e `tools/executar_geoai.py`._", ""]
    o = r["verificacao_osm"]
    L += ["## 8. Verificação cruzada com edificações do OpenStreetMap", "", o["nota"] + ".", "",
          f"- Área de edificações do OSM nas {o['celulas']:,} células: {n(o['soma_osm_km2'], 1)} km²; Profill (Edificação): {n(o['soma_profill_edificacao_km2'], 1)} km² (razão {n(o['razao_osm_sobre_profill_edificacao'], 3)}).".replace(",", "."),
          f"- Correlação célula a célula: OSM × Profill-Edificação {n(o['corr_osm_x_profill_edificacao'], 3)} (MAE {n(o['mae_osm_x_profill_edificacao'], 4)}); OSM × Profill-construído {n(o['corr_osm_x_profill_construido'], 3)}; OSM × estimativa {n(o['corr_osm_x_previsto_construido'], 3)}; Profill-construído × estimativa {n(o['corr_profill_construido_x_previsto'], 3)}.",
          "- Leitura: a coerência entre OSM e Profill é alta, o que **não** prova independência (as importações do OSM podem ter vindo de mapas municipais). A estimativa correlaciona menos com o OSM do que a própria Profill, como esperado: o OSM só tem edificações, e o alvo inclui vias pavimentadas.", ""]
    L += ["## 9. Critérios operacionais propostos no relatório de viabilidade", "", "Critérios **operacionais** definidos antes da execução, sem fundamento normativo; servem para decidir o uso neste projeto, não como padrão científico.", "", "| Critério | Limite | Resultado | Situação |", "|---|---|---|---|"]
    b = p1[nome_prim]["bootstrap_por_blocos"]
    ok1 = b["mae"]["valor"] <= lim["mae_fracao_construida"]
    ok2 = abs(b["vies"]["valor"]) <= lim["vies_absoluto"]
    ok3 = ba["fracao_dentro_do_limite"] >= lim["fracao_de_bairros_dentro_do_limite"]
    mae2 = p2[nome_prim]["bootstrap_por_blocos"]["mae"]["valor"] <= lim["mae_fracao_construida"]
    L += [f"| MAE da fração construída, P1 | ≤ {n(lim['mae_fracao_construida'], 2)} | {ic(b['mae'])} | {'cumprido' if ok1 else 'não cumprido'} |",
          f"| Viés absoluto, P1 | ≤ {n(lim['vies_absoluto'], 2)} | {ic(b['vies'])} | {'cumprido' if ok2 else 'não cumprido'} |",
          f"| MAE da fração construída, P2 (quadrante fora) | ≤ {n(lim['mae_fracao_construida'], 2)} | {ic(p2[nome_prim]['bootstrap_por_blocos']['mae'])} | {'cumprido' if mae2 else 'não cumprido'} |",
          f"| Bairros com erro de área ≤ {n(100 * lim['erro_de_area_por_bairro'], 0)}% | ≥ {n(100 * lim['fracao_de_bairros_dentro_do_limite'], 0)}% dos bairros | {n(100 * ba['fracao_dentro_do_limite'], 1)}% | {'cumprido' if ok3 else 'não cumprido'} |",
          f"| Blocos com MAE ≤ {n(lim['mae_fracao_construida'], 2)} | ≥ {n(100 * lim['fracao_de_bairros_dentro_do_limite'], 0)}% dos blocos | {n(100 * est['fracao_de_blocos_dentro_do_limite'], 1)}% | {'cumprido' if est['fracao_de_blocos_dentro_do_limite'] >= lim['fracao_de_bairros_dentro_do_limite'] else 'não cumprido'} |"]
    if "rf_AEF" in p1:
        d = r["comparacao_pareada_com_o_primario"]["rf_AEF"]
        dm = p1["rf_AEF"]["bootstrap_por_blocos"]["macro_f1"]["valor"] - p1[nome_prim]["bootstrap_por_blocos"]["macro_f1"]["valor"]
        L.append(f"| Ganho do foundation model (AlphaEarth) sobre o Random Forest | MAE menor com IC que exclui zero, ou +{n(lim['ganho_minimo_de_macro_f1'], 2)} de macro F1 | MAE {n(d['diferenca_mae'], 4)} [{n(d['ic95'][0], 4)}; {n(d['ic95'][1], 4)}]; macro F1 {n(dm, 3)} | "
                 + ("ganho demonstrado no MAE" if d["ic95"][1] < 0 else "sem ganho demonstrado") + " |")
    L += ["", "## 10. Produto e rastreabilidade", "", f"- COG: `{man['produto']['arquivo']}` ({', '.join(man['produto']['bandas'])}), SHA-256 `{man['produto']['sha256'][:16]}…`. Fora do Git.",
          f"- Modelo: {man['modelo']['nome']} ({man['modelo']['biblioteca']}), conjunto `{man['modelo']['conjunto_de_atributos']}`, sem pesos pré-treinados.", f"- Dependências: " + ", ".join(f"{k} {v}" for k, v in man["dependencias"].items()) + ".", ""]
    (RAIZ / "docs/geoai_resultados.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("gravado:", RAIZ / "docs/geoai_resultados.md")


if __name__ == "__main__":
    main()
