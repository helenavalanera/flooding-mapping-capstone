# -*- coding: utf-8 -*-
"""Gera as figuras explicativas da apresentação curta (fluxo, valor por público, números-chave) em docs/figuras.

    python tools/gerar_figuras_apresentacao.py     # precisa de matplotlib (já usado pelo pipeline)

Só desenha esquemas e números que constam dos relatórios do projeto (26,2 mm, 14 dias/ano, 3,5%, 7%, 190 mil pessoas).
Nada aqui é captura de tela nem dado inventado.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

SAIDA = Path(__file__).resolve().parents[1] / "docs" / "figuras"
PETROLEO, AZUL, ALERTA, VERDE, TINTA, MUDO = "#0F3F4A", "#0B5D8F", "#C27A00", "#1B7F5C", "#1B2630", "#5A6872"
FUNDO, CARD, LINHA = "#FFFFFF", "#F2F6F8", "#D5DDE2"
plt.rcParams["font.family"] = "DejaVu Sans"


def tela(w=13.0, h=4.0):
    fig = plt.figure(figsize=(w, h), dpi=200, facecolor=FUNDO)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


def cartao(ax, x, y, w, h, cor=CARD, borda=LINHA):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=cor, ec=borda, lw=1.2))


def fluxo():
    fig, ax = tela(13.0, 3.5)
    etapas = [
        ("1", "Chuva", "previsão horária\ne histórico (reanálise)", AZUL),
        ("2", "Terreno e ruas", "relevo Copernicus e\nrede OpenStreetMap", AZUL),
        ("3", "Trechos expostos", "regra explícita:\nnada fecha abaixo\nde 26,2 mm", ALERTA),
        ("4", "Áreas e lugares", "bolsões de exposição\ne 1.720 pontos de\ninteresse dentro deles", PETROLEO),
        ("5", "Comunidade", "confirma ou diz que\nsecou; nada interdita\numa rua sozinho", VERDE),
        ("6", "Aprende e sugere", "ranking de onde\nverificar primeiro,\nnão previsão", VERDE),
    ]
    n, larg, gap = len(etapas), 1.8, 0.32
    x0 = (13.0 - (n * larg + (n - 1) * gap)) / 2
    for i, (num, tit, sub, cor) in enumerate(etapas):
        x = x0 + i * (larg + gap)
        cartao(ax, x, 0.7, larg, 2.5)
        ax.add_patch(plt.Circle((x + 0.33, 2.85), 0.2, color=cor))
        ax.text(x + 0.33, 2.85, num, color="white", ha="center", va="center", fontsize=12, fontweight="bold")
        ax.text(x + larg / 2, 2.25, tit, ha="center", va="center", fontsize=11, fontweight="bold", color=TINTA)
        ax.text(x + larg / 2, 1.45, sub, ha="center", va="center", fontsize=9.6, color=MUDO, linespacing=1.4)
        if i < n - 1:
            ax.annotate("", xy=(x + larg + gap - 0.03, 1.95), xytext=(x + larg + 0.03, 1.95),
                        arrowprops=dict(arrowstyle="-|>", color=MUDO, lw=1.6))
    ax.text(6.5, 0.32, "Cada etapa diz o que é observado, estimado ou simulado. Nenhuma rota é apresentada como segura.",
            ha="center", va="center", fontsize=10, color=MUDO, style="italic")
    fig.savefig(SAIDA / "apresentacao_fluxo_chuva_decisao.png"); plt.close(fig)


def valor():
    fig, ax = tela(13.0, 4.2)
    colunas = [
        ("Quem sai de casa", "O que a chuva pode afetar\nperto de mim, nas próximas horas?",
         ["avisos dos lugares que salvei", "hospitais e escolas dentro da área", "rota com menor exposição estimada"], AZUL),
        ("Quem viu a rua alagada", "Ainda está alagado\nou já secou?",
         ["confirmo ou digo que secou", "meu apoio prioriza a verificação", "não interdita rua nenhuma"], VERDE),
        ("Quem cuida da cidade", "Onde a perda de acesso\né maior?",
         ["mapa de mobilidade perdida", "áreas em que a perda chega a 79%", "método aberto e replicável"], PETROLEO),
    ]
    larg, gap = 3.9, 0.35
    x0 = (13.0 - (3 * larg + 2 * gap)) / 2
    for i, (quem, pergunta, itens, cor) in enumerate(colunas):
        x = x0 + i * (larg + gap)
        cartao(ax, x, 0.3, larg, 3.6)
        ax.add_patch(FancyBboxPatch((x, 3.3), larg, 0.6, boxstyle="round,pad=0,rounding_size=0.12", fc=cor, ec=cor))
        ax.text(x + larg / 2, 3.6, quem, ha="center", va="center", color="white", fontsize=13.5, fontweight="bold")
        ax.text(x + larg / 2, 2.75, pergunta, ha="center", va="center", fontsize=10.8, color=TINTA, fontweight="bold", linespacing=1.4)
        for j, t in enumerate(itens):
            ax.text(x + 0.3, 1.9 - j * 0.5, "•  " + t, ha="left", va="center", fontsize=10.3, color=MUDO)
    fig.savefig(SAIDA / "apresentacao_valor_por_publico.png"); plt.close(fig)


def numeros():
    fig, ax = tela(13.0, 3.4)
    itens = [
        ("14 dias/ano", "chuva igual ou acima de 26,2 mm,\nem média\n(2015–2024; variação 8 a 21)", AZUL),
        ("26,2 mm", "menor acumulado em 24 h que já\ncoincidiu com bloqueios da EPTC", ALERTA),
        ("3,5% → 7%", "mobilidade de carro perdida:\n26–35 mm e 40–45 mm", PETROLEO),
        ("190 mil", "pessoas perdem ao menos 10%\ndo que alcançam (40–45 mm)", VERDE),
    ]
    larg, gap = 2.9, 0.3
    x0 = (13.0 - (4 * larg + 3 * gap)) / 2
    for i, (grande, legenda, cor) in enumerate(itens):
        x = x0 + i * (larg + gap)
        cartao(ax, x, 0.35, larg, 2.7)
        ax.text(x + larg / 2, 2.2, grande, ha="center", va="center", fontsize=25, fontweight="bold", color=cor)
        ax.text(x + larg / 2, 1.1, legenda, ha="center", va="center", fontsize=10, color=MUDO, linespacing=1.45)
    fig.savefig(SAIDA / "apresentacao_numeros_chave.png"); plt.close(fig)


if __name__ == "__main__":
    fluxo(); valor(); numeros()
    print("figuras gravadas em", SAIDA)
