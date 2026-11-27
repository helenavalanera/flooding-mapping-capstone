"""Índice da documentação (docs/README.md) e pasta única de documentação pronta para upload (documentacao_final/).

    PYTHONPATH=src .venv/bin/python tools/consolidar_documentacao.py [--so-indice] [--saida DIR]

Cada documento de ``docs/`` tem aqui o nome, a finalidade e a categoria (um teste confere que nenhum documento fica sem entrada nem aponta para arquivo que não existe).
- ``docs/README.md``: o índice (nome, finalidade e localização), versionado, sem duplicar nada.
- ``documentacao_final/`` (fora do Git): uma pasta só, com os documentos, o leia-me, os relatórios e números que os sustentam e o índice, mais ``MANIFESTO.json`` (SHA-256 de cada arquivo).
  É para o backup manual (por exemplo, no Google Drive); esta ferramenta não envia nada nem gera ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
CATEGORIAS = ["Produto, método e resultados", "Dados, fontes e base legal", "GeoAI (camada E)", "Publicação, infraestrutura e cache", "Qualidade, auditorias e requisitos", "Apresentação e proposta", "Histórico: frentes arquivadas"]
# nome do arquivo -> (categoria, finalidade)
CATALOGO = {
    "metodologia.md": (0, "Metodologia consolidada: fórmula, métodos 1 e 2, limites físicos, hipóteses e validações."),
    "fase3_motor.md": (0, "O motor de contribuição potencial e o indicador topográfico (dimensões A, B e C)."),
    "fase3_entradas_e_saidas.md": (0, "Entradas e saídas da Fase 3: proposta original e o que foi implementado."),
    "fase3_resultados.md": (0, "Resultados da execução da Fase 3 (gerado)."),
    "fase4_integracao.md": (0, "A camada de escoamento potencial na aplicação: formato de distribuição e regras da tela."),
    "recorte_municipal.md": (0, "Recorte municipal: só as ruas dentro de Porto Alegre (143.149 trechos), efeito nos números e como reproduzir."),
    "resultados_executivos.md": (0, "Resultados executivos da aba Resultados."),
    "sensibilidade_hidrologica.md": (0, "Sensibilidade hidrológica: a física simplificada acrescenta informação ao índice atual?"),
    "robustez_espacial.md": (0, "Robustez da validação espacial por blocos."),
    "modelo_retencao_viabilidade.md": (0, "Viabilidade do modelo de acúmulo superficial: o que os dados sustentam."),
    "mapa_simulador_pwa.md": (0, "Mapa de análise, simulador e auditoria final (26/11/2026)."),
    "landing_estudo.md": (0, "A landing: oito seções, mapas de manchas, geração a partir dos relatórios e regras de redação."),
    "mapa_base.md": (0, "Mapa-base (Protomaps): arquivo, estilos, fontes e licenças."),
    "glossario.md": (0, "Glossário oficial de nomenclaturas e termos proibidos."),
    "sintese_academica.md": (5, "Síntese acadêmica: resultados, limites e conclusão."),
    "inventario_fontes.md": (1, "Inventário de fontes, dados derivados e ferramentas."),
    "inventario_fontes_poa.md": (1, "Matriz de disponibilidade das fontes de Porto Alegre (25/11/2026)."),
    "catalogo_dados.md": (1, "Catálogo do acervo: origem, derivados, layout no R2 e condição de acesso."),
    "base_legal_dados.md": (1, "Decreto Municipal 20.315/2019 invocado, origem de cada conjunto da Prefeitura e atribuição."),
    "referencias_bibliograficas.md": (1, "Referências bibliográficas do estudo (ABNT)."),
    "qualidade_dados_fase2.md": (1, "Qualidade dos dados integrados e cobertura territorial (Fase 2)."),
    "auditoria_fontes_drenagem_poa.md": (1, "Auditoria das fontes municipais de drenagem, uso do solo, relevo e risco."),
    "geoai_camada_e.md": (2, "A camada E no produto: o que é, o que não é, resultados, limites, arquivos e como gerar."),
    "geoai_fase5.md": (2, "Fase 5: o experimento GeoAI (decisão, aderência, fontes, limites e pendências)."),
    "geoai_resultados.md": (2, "Resultados do experimento GeoAI (gerado a partir de reports/qa/geoai_resultados.json)."),
    "deploy_cloudflare.md": (3, "Publicação no Cloudflare Pages (aplicação) e R2 (dados): passo a passo."),
    "r2_cache.md": (3, "R2, cache HTTP e CDN: preparação dos objetos, cabeçalhos, validação e medições."),
    "publicacao_pages_releases.md": (3, "Arquitetura de publicação: Pages, Releases e distribuição de dados."),
    "auditoria_escopo_porto_alegre.md": (4, "Auditoria de escopo: o produto ativo é só Porto Alegre."),
    "auditoria_final_2026-11.md": (4, "Auditoria final, testes e preparação para 01/12/2026."),
    "fase41_auditoria.md": (4, "Fase 4.1: auditoria, desempenho e preparação para a demonstração."),
    "qa_relatorio_final.md": (4, "Relatório final de QA e matrizes de aceite."),
    "capstone_requisitos.md": (4, "Aderência aos requisitos oficiais do Capstone (FTL Brasil)."),
    "proposta.md": (5, "Proposta do projeto final (FTL Brasil, Space Tech Bootcamp 2026)."),
    "roteiro_apresentacao.md": (5, "Roteiro de apresentação do capstone."),
    "roteiro_apresentacao_curta.md": (5, "Roteiro da apresentação curta (template FTL)."),
    "demonstracao.md": (5, "Demonstração controlada: do preparo ao encerramento."),
    "ROADMAP.md": (6, "Roadmap histórico (escopo estadual)."),
    "avisos_comunidade.md": (6, "Avisos ao cidadão e laço da comunidade (frente de mobilidade arquivada)."),
    "coletor_crbm.md": (6, "Coletor dos bloqueios da CPRv BM (frente estadual arquivada)."),
    "events_contract.md": (6, "Contrato de dados de eventos e cenários (frente anterior)."),
    "extracao.md": (6, "Extração de eventos a partir de texto (Fase 1, arquivada)."),
    "guia_de_uso.md": (6, "Guia de uso do painel e do PWA (PWA arquivado)."),
    "hospedagem.md": (6, "Hospedagem do servidor (frente anterior)."),
    "render.md": (6, "Hospedagem no Render: preparação, custos e checklist (frente anterior)."),
    "ml_gatilho.md": (6, "Gatilho municipal de risco hídrico (frente estadual arquivada)."),
    "operacao_ocorrencias.md": (6, "Operação de ocorrências (frente de monitoramento arquivada)."),
    "produto_preventivo.md": (6, "Inteligência territorial e mobilidade preventiva (frente arquivada)."),
    "proposta_assistente_territorial.md": (6, "Proposta de assistente territorial (futuro, não implementado)."),
    "publicacao.md": (6, "Publicação da interface estadual no GitHub Pages (arquivada)."),
    "qa_mobile_fisico.md": (6, "QA em dispositivo físico (PWA arquivado)."),
    "seguranca_lgpd.md": (6, "Segurança e proteção de dados da frente de rotas e relatos (arquivada)."),
    "validacao_gemini.md": (6, "Validação do provedor de linguagem (frente de extração arquivada)."),
}
EXTRAS = [("README.md", "Visão geral do projeto, como rodar e a tabela de fontes."), ("LICENSE", "Licença do código (MIT).")]


def titulo(p: Path) -> str:
    for linha in p.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#"):
            return linha.lstrip("# ").strip()
    return p.stem


def indice(prefixo_docs: str = "") -> str:
    """O índice em Markdown. ``prefixo_docs``: como os documentos são citados (vazio em docs/README.md; ``documentos/`` na pasta de upload)."""
    L = ["# Índice da documentação", "",
         "Nome, finalidade e localização de cada documento do Flooding Mapping. Os documentos de **Histórico** descrevem frentes anteriores (escopo estadual, mobilidade, PWA, gatilho municipal) que foram arquivadas e não fazem parte do produto atual. "
         "Os números vigentes estão em `reports/qa/` e em `src/flooding_mapping/app/static/data/` (copiados para `numeros-e-relatorios/` na pasta de upload).", ""]
    for i, cat in enumerate(CATEGORIAS):
        itens = sorted((n for n, (c, _) in CATALOGO.items() if c == i), key=str.lower)
        if not itens:
            continue
        L += [f"## {cat}", "", "| Documento | Finalidade | Localização |", "|---|---|---|"]
        for n in itens:
            L.append(f"| [{titulo(DOCS / n)}]({prefixo_docs}{n}) | {CATALOGO[n][1]} | `docs/{n}` |")
        L.append("")
    L += ["## Raiz do repositório", "", "| Arquivo | Finalidade | Localização |", "|---|---|---|"] + [f"| `{n}` | {f} | `{n}` |" for n, f in EXTRAS] + [""]
    return "\n".join(L)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pasta_unica(saida: Path) -> dict:
    shutil.rmtree(saida, ignore_errors=True)
    (saida / "documentos").mkdir(parents=True)
    for p in sorted(DOCS.glob("*.md")):
        shutil.copy(p, saida / "documentos" / p.name)
    if (DOCS / "figuras").exists():
        shutil.copytree(DOCS / "figuras", saida / "documentos" / "figuras")
    (saida / "leia-me").mkdir()
    for n, _ in EXTRAS:
        shutil.copy(RAIZ / n, saida / "leia-me" / n)
    for origem, destino in (("reports/qa", "numeros-e-relatorios/qa"), ("src/flooding_mapping/app/static/data", "numeros-e-relatorios/dados-publicados")):
        (saida / destino).mkdir(parents=True, exist_ok=True)
        for p in sorted((RAIZ / origem).glob("*.json")):
            shutil.copy(p, saida / destino / p.name)
    (saida / "INDICE.md").write_text(indice("documentos/").replace("`docs/", "`documentos/").replace("`README.md` |", "`leia-me/README.md` |").replace("`LICENSE` |", "`leia-me/LICENSE` |") + "\n", encoding="utf-8")
    arquivos = {p.relative_to(saida).as_posix(): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(saida.rglob("*")) if p.is_file()}
    (saida / "MANIFESTO.json").write_text(json.dumps({"arquivos": len(arquivos), "bytes": sum(a["bytes"] for a in arquivos.values()), "conteudo": arquivos}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"arquivos": len(arquivos), "mb": round(sum(a["bytes"] for a in arquivos.values()) / 1e6, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--so-indice", action="store_true")
    ap.add_argument("--saida", type=Path, default=RAIZ / "documentacao_final")
    a = ap.parse_args()
    (DOCS / "README.md").write_text(indice() + "\n", encoding="utf-8")
    print("docs/README.md gravado")
    if not a.so_indice:
        print("pasta única:", json.dumps(pasta_unica(a.saida)), "em", a.saida)


if __name__ == "__main__":
    main()
