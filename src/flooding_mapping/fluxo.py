"""Roteamento D8 como uma FLORESTA: cada célula tem no máximo um receptor, então o fluxo forma árvores cujas raízes são os exutórios.

Essa estrutura dá, sem laços em Python sobre o acúmulo:

* acúmulo exato de qualquer grandeza (área, volume, várias colunas de uma vez) = soma da sub-árvore de cada célula (soma de prefixos sobre a ordem de visita de uma busca em profundidade);
* teste de ancestralidade em O(1) ("a célula d está no caminho de escoamento da célula c?"), que é o que permite associar contribuições a trechos sem contar a mesma água duas vezes;
* conservação de massa verificável: a soma do acumulado nas raízes é igual à soma dos pesos.

O receptor de cada célula é o vizinho de maior declividade (D8) com queda estritamente positiva; as regras de empate são as mesmas de ``susceptibility.flow_accumulation``, e os testes
conferem que o acúmulo com peso 1 reproduz aquela função. Células sem receptor (borda do raster, vizinhas de NaN ou mínimos) são EXUTÓRIOS: a água sai do modelo ali. As depressões devem
ter sido preenchidas antes (``susceptibility.fill_depressions``): este módulo roteia, não armazena.
"""
from __future__ import annotations

import numpy as np

OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def receptores_d8(preenchido: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Flat index of the receiver of each cell (-1 where the cell is an outlet or has no data) and the mask of cells with data."""
    linhas, colunas = preenchido.shape
    z = np.where(np.isnan(preenchido), np.inf, preenchido)
    acolchoado = np.pad(z, 1, constant_values=np.inf)
    maior_queda = np.zeros(z.shape)
    receptor = np.full(z.shape, -1, dtype=np.int64)
    indice = np.arange(z.size).reshape(z.shape)
    for dr, dc in OFFSETS:
        vizinho = acolchoado[1 + dr:1 + dr + linhas, 1 + dc:1 + dc + colunas]
        with np.errstate(invalid="ignore"):                       # inf - inf nas células sem dado: nunca são receptoras
            queda = (z - vizinho) / np.hypot(dr, dc)
        melhor = np.isfinite(vizinho) & (queda > maior_queda)
        maior_queda[melhor] = queda[melhor]
        alvo = np.roll(np.roll(indice, -dr, axis=0), -dc, axis=1)
        receptor[melhor] = alvo[melhor]
    valida = ~np.isnan(preenchido)
    receptor = np.where(valida, receptor, -1)
    return receptor.ravel(), valida.ravel()


class ArvoreDeFluxo:
    """The flow forest: ``tin``/``tout`` bracket each cell's sub-tree in the visiting order, ``visita`` lists the cells in that order."""

    def __init__(self, receptor: np.ndarray, valida: np.ndarray):
        n = len(receptor)
        self.n, self.receptor, self.valida = n, receptor, valida
        idx = np.arange(n)
        pai = np.where(valida & (receptor >= 0), receptor, -1)
        com_pai = idx[pai >= 0]
        filhos = com_pai[np.argsort(pai[com_pai], kind="stable")]
        ini = np.concatenate([[0], np.cumsum(np.bincount(pai[com_pai], minlength=n))]).tolist()
        raizes = idx[valida & (pai < 0)].tolist()
        filhos_l = filhos.tolist()
        tin, tout = [-1] * n, [-1] * n
        visita, proximo = [], ini[:-1]
        for raiz in raizes:
            tin[raiz] = len(visita)
            visita.append(raiz)
            pilha = [raiz]
            while pilha:
                v = pilha[-1]
                p = proximo[v]
                if p < ini[v + 1]:
                    proximo[v] = p + 1
                    f = filhos_l[p]
                    tin[f] = len(visita)
                    visita.append(f)
                    pilha.append(f)
                else:
                    tout[v] = len(visita) - 1
                    pilha.pop()
        self.tin, self.tout = np.array(tin, dtype=np.int64), np.array(tout, dtype=np.int64)
        self.visita = np.array(visita, dtype=np.int64)
        self.raizes = np.array(raizes, dtype=np.int64)
        if len(self.visita) != int(valida.sum()):
            raise RuntimeError("o fluxo tem um laço: o receptor deve ser sempre estritamente mais baixo (preencha as depressões antes)")

    def acumular(self, pesos: np.ndarray) -> np.ndarray:
        """Sum of ``pesos`` over each cell's upstream catchment, itself included. ``pesos`` is (n,) or (n, K); cells without data get NaN. Each cell counts once."""
        p = np.asarray(pesos, dtype=float)
        um_d = p.ndim == 1
        p = p[:, None] if um_d else p
        if p.shape[0] != self.n:
            raise ValueError("pesos com tamanho diferente do raster")
        if np.isnan(p[self.valida]).any():
            raise ValueError("pesos com NaN em célula válida")
        prefixo = np.vstack([np.zeros((1, p.shape[1])), np.cumsum(p[self.visita], axis=0)])
        acc = np.full(p.shape, np.nan)
        v = self.visita
        acc[v] = prefixo[self.tout[v] + 1] - prefixo[self.tin[v]]
        return acc[:, 0] if um_d else acc

    def exutorios(self) -> np.ndarray:
        return self.raizes

    def conservacao(self, pesos: np.ndarray, acumulado: np.ndarray | None = None) -> dict:
        """Mass balance: what leaves through the outlets must equal what was generated. Relative error per column."""
        p = np.asarray(pesos, dtype=float)
        p = p[:, None] if p.ndim == 1 else p
        acc = self.acumular(p) if acumulado is None else (np.asarray(acumulado)[:, None] if np.asarray(acumulado).ndim == 1 else np.asarray(acumulado))
        gerado = p[self.valida].sum(axis=0)
        saiu = acc[self.raizes].sum(axis=0)
        erro = np.abs(saiu - gerado) / np.where(gerado == 0, 1.0, gerado)
        return {"gerado": gerado.tolist(), "saiu_pelos_exutorios": saiu.tolist(), "erro_relativo_maximo": float(erro.max()) if erro.size else 0.0}

    def eh_ancestral(self, a: np.ndarray, c: np.ndarray) -> np.ndarray:
        """True where cell ``a`` lies on the downstream path of cell ``c`` (a is an ancestor of c in the forest, a != c)."""
        a, c = np.asarray(a), np.asarray(c)
        return (a != c) & (self.tin[a] < self.tin[c]) & (self.tout[c] <= self.tout[a])
