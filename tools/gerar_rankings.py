"""Rankings e média mensal da landing, só por agregação dos resultados que já existem (nada reexecuta o motor).

    PYTHONPATH=src .venv/bin/python tools/gerar_rankings.py

Lê: static/data/resultados_poa.json (bairros) e a série diária de Porto Alegre (data/raw/weather/archive, a mesma de resultados.py).
Escreve: static/data/rankings_poa.json, com o que é publicado e o motivo do que não é.
Nunca soma a contribuição acumulada entre trechos: usa as parcelas e medianas por bairro que resultados.py já calculou, e só de bairros com trechos suficientes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from flooding_mapping import resultados  # noqa: E402

SAIDA = RAIZ / "src/flooding_mapping/app/static/data/rankings_poa.json"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def media_mensal() -> dict:
    s = resultados.serie_diaria(RAIZ / "data/raw/weather/archive")
    mensal = s.groupby([s.index.year, s.index.month]).sum()
    dias = s.groupby([s.index.year, s.index.month]).size()
    completos = [(a, m) for (a, m), n in dias.items() if n == pd_dias(a, m)]   # só meses inteiros: o mês corrente da série fica de fora
    por_mes = {m: [float(mensal[(a, mm)]) for a, mm in completos if mm == m] for m in range(1, 13)}
    return {"fonte": "Open-Meteo, arquivo de reanálise (base ERA5), total diário no ponto da grade de Porto Alegre; modelada, não é pluviômetro; a grade suaviza e subestima extremos locais",
            "periodo_da_serie": [str(s.index.min().date()), str(s.index.max().date())],
            "o_que_e": "média, entre os anos, do total de chuva de cada mês do calendário (mm por mês). Não é chuva por evento nem por dia",
            "meses": [{"mes": MESES[m - 1], "media_mm": round(sum(v) / len(v), 1), "anos": len(v)} for m, v in por_mes.items()],
            "media_dos_meses_mm": round(float(sum(sum(v) for v in por_mes.values()) / sum(len(v) for v in por_mes.values())), 1)}


def pd_dias(ano: int, mes: int) -> int:
    import calendar
    return calendar.monthrange(ano, mes)[1]


def top_bairros(n: int = 5) -> dict:
    b = json.loads((RAIZ / "src/flooding_mapping/app/static/data/resultados_poa.json").read_text(encoding="utf-8"))["bairros"]
    validos = [x for x in b if x["suficiente"]]
    ordem = sorted(validos, key=lambda x: (-x["parcela_com_preenchimento"], x["nome"]))[:n]
    return {"criterio": "parcela dos trechos de rua do bairro com propensão topográfica à retenção, isto é, em que o relevo favorece o acúmulo de água segundo o modelo de 30 m (indicador relativo; não é profundidade, volume nem duração, e não confirma alagamento)",
            "universo": f"{len(validos)} dos {len(b)} bairros: só os com trechos suficientes (os demais ficam de fora, sem estimativa)",
            "itens": [{"posicao": i + 1, "bairro": x["nome"], "parcela_com_propensao_topografica": round(x["parcela_com_preenchimento"], 3),
                       "parcela_no_decil_superior_de_contribuicao": round(x["parcela_no_decil_superior_da_cidade"], 3), "trechos_com_dados": x["trechos_com_dados"],
                       "cobertura_do_coeficiente_a_montante_mediana": round(x["cobertura_m1_a_montante_mediana"], 2)} for i, x in enumerate(ordem)]}


def main() -> None:
    r = {"media_mensal_de_chuva": media_mensal(), "top5_bairros": top_bairros(),
         "nao_publicados": {
             "top10_trechos": "A contribuição acumulada se repete ao longo de um mesmo caminho da água: trechos vizinhos da mesma rede carregam a mesma água, então os valores não se somam e ordená-los em uma lista de ruas induziria a leitura errada. Sem um critério metodológico validado para ordenar trechos, o estudo mostra os mapas e os bairros, e não um ranking de ruas.",
             "ranking_de_zonas": "Não há, nos dados do projeto, divisão de Porto Alegre em zonas (só os 94 bairros). Criar uma agrupando bairros seria inventar uma classificação."}}
    SAIDA.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print("gravado:", SAIDA)


if __name__ == "__main__":
    main()
