"""Gera as referências bibliográficas a partir de config/referencias.yaml (fonte única) e oferece as funções de citação usadas pela landing.

    PYTHONPATH=src .venv/bin/python tools/gerar_referencias.py

Saída: docs/referencias_bibliograficas.md. A seção "Referências bibliográficas" da landing e as citações da landing usam as mesmas funções (tools/gerar_landing.py).

Formato: estrutura de referência da NBR 6023 (autoria, título em destaque, subtítulo, edição ou versão, local, editora, ano, DOI, "Disponível em:", "Acesso em:") e sistema autor-data da
NBR 10520 para as citações. ATENÇÃO: a edição vigente dessas normas não pôde ser confirmada nesta revisão (o catálogo da ABNT exige consulta interativa e os textos são pagos); a
forma adotada reúne o que é comum às edições conhecidas e precisa ser conferida pela autora contra a edição vigente (docs/referencias_bibliograficas.md, "Normalização").
"""
import html
import re
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "config" / "referencias.yaml"
CATEGORIAS = {1: "Dados geoespaciais e bases territoriais", 2: "Dados de uso e cobertura do solo", 3: "Dados de relevo e modelos digitais de elevação", 4: "Dados de drenagem e infraestrutura urbana",
              5: "Dados meteorológicos e precipitação", 6: "Bases históricas e registros de eventos", 7: "Dados de referência e validação", 8: "Métodos e referenciais científicos",
              9: "Modelos de inteligência artificial e GeoAI", 10: "Bibliotecas, ferramentas e tecnologias", 11: "Mapas-base, serviços cartográficos e provedores"}
USO = {"efetiva": "Utilizada", "experimento": "Utilizada em experimento", "historica": "Frente arquivada (mobilidade e painel estadual)", "avaliada": "Avaliada, não utilizada", "planejada": "Planejada para etapas futuras, ainda não utilizada"}
SEPARADAS = ("avaliada", "planejada")   # não são metodologia executada: aparecem à parte
TIPOS = {"artigo", "preprint", "software", "dataset", "documento", "web"}
MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
OBRIGATORIOS = ("id", "cat", "uso", "tipo", "autor", "titulo", "ano", "licenca", "nota", "conferido")


def carregar() -> list[dict]:
    refs = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8"))["referencias"]
    ids = [r["id"] for r in refs]
    assert len(ids) == len(set(ids)), "ids repetidos"
    for r in refs:
        faltam = [c for c in OBRIGATORIOS if c not in r]
        assert not faltam, (r["id"], faltam)
        assert r["cat"] in CATEGORIAS and r["uso"] in USO and r["tipo"] in TIPOS, r["id"]
    return refs


def data_abnt(iso: str) -> str:
    a, m, d = iso.split("-")
    return f"{int(d)} {MESES[int(m) - 1]} {a}"


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def ordenar(refs: list[dict]) -> list[dict]:
    return sorted(refs, key=lambda r: (_sem_acento(r["autor"]), r["ano"], _sem_acento(r["titulo"])))


def citacao(r: dict) -> str:
    """Chave da citação no texto (NBR 10520, autor-data), como no campo cit do registro."""
    return r["cit"]


def partes(r: dict) -> list[tuple[str, str]]:
    """Referência como lista de (estilo, texto); estilo 'b' é o elemento em destaque (título da obra ou do periódico)."""
    p: list[tuple[str, str]] = []
    autor = r["autor"].rstrip(".")
    p.append(("t", autor + ". "))
    sub = r.get("subtitulo")
    titulo = r["titulo"]
    t = r["tipo"]
    if t == "artigo":
        p += [("t", titulo + ". "), ("b", r["periodico"]), ("t", ", ")]
        if r.get("vol"):
            p.append(("t", f"v. {r['vol']}, "))
        if r.get("num"):
            p.append(("t", f"n. {r['num']}, "))
        if r.get("pag"):
            p.append(("t", f"p. {r['pag']}, "))
        p.append(("t", f"{r['ano']}. "))
    else:
        p.append(("b", titulo))
        p.append(("t", (": " + sub if sub else "") + ". "))
        if t == "preprint":
            p.append(("t", f"{r['ano']}. Pré-publicação (arXiv). "))
        else:
            if r.get("versao"):
                p.append(("t", f"Versão {r['versao']}. "))
            local, ed = r.get("local"), r.get("editora")
            if local or ed:
                p.append(("t", f"{local or '[S. l.]'}: {ed or '[s. n.]'}, {r['ano']}. "))
            else:
                p.append(("t", f"{r['ano']}. "))
            if t == "software":
                p.append(("t", "Software. "))
            elif t == "dataset":
                p.append(("t", "Conjunto de dados. "))
    if r.get("doi"):
        p.append(("t", f"DOI: {r['doi']}. "))
    link = r.get("url") or (f"https://doi.org/{r['doi']}" if r.get("doi") else None)
    if link:
        p.append(("t", "Disponível em: "))
        p.append(("u", link))
        p.append(("t", ". "))
        if r.get("acesso"):
            p.append(("t", f"Acesso em: {data_abnt(r['acesso'])}."))
        if r.get("verificado") is False:
            p.append(("t", " [endereço não verificado por acesso automatizado]"))
    else:
        p.append(("t", "Sem endereço público."))
    return p


def _md(partes_: list[tuple[str, str]]) -> str:
    return "".join(f"**{x}**" if e == "b" else (f"<{x}>" if e == "u" else x) for e, x in partes_).strip()


def _html(partes_: list[tuple[str, str]]) -> str:
    out = []
    for e, x in partes_:
        if e == "b":
            out.append(f"<b>{html.escape(x)}</b>")
        elif e == "u":
            out.append(f'<a href="{html.escape(x, quote=True)}" rel="noopener">{html.escape(x)}</a>')
        else:
            out.append(html.escape(x))
    return "".join(out).strip()


def citar(ids: list[str], refs: list[dict], como_html: bool = True) -> str:
    """Citação autor-data com um ou vários trabalhos, em ordem alfabética e separados por ponto e vírgula."""
    por_id = {r["id"]: r for r in refs}
    itens = sorted((por_id[i] for i in ids), key=lambda r: _sem_acento(citacao(r)))
    chaves = [citacao(r) for r in itens]
    if len(chaves) > 1:   # (A, 2020; B, 2021)
        texto = "(" + "; ".join(chaves) + ")"
    else:
        texto = f"({chaves[0]})"
    if not como_html:
        return texto
    links = "; ".join(f'<a class="cit" href="#ref-{r["id"]}">{html.escape(citacao(r))}</a>' for r in itens)
    return f"({links})"


def substituir_citacoes(texto: str, refs: list[dict]) -> str:
    """Troca {{cite:id1,id2}} pela citação com link para a referência."""
    def troca(m: re.Match) -> str:
        return citar([i.strip() for i in m.group(1).split(",")], refs)
    return re.sub(r"\{\{cite:([a-z0-9_,\s]+)\}\}", troca, texto)


def linha_uso(r: dict, como_html: bool) -> str:
    base = f"{USO[r['uso']]}. Licença ou condição de uso: {r['licenca']}. {r['nota']}"
    return html.escape(base) if como_html else base


def bloco_html(refs: list[dict]) -> str:
    """As categorias como <details> (alcançáveis por âncora; estudo.js abre a que contém o destino) e as tecnologias avaliadas à parte."""
    out = []
    for n, nome in CATEGORIAS.items():
        itens = ordenar([r for r in refs if r["cat"] == n and r["uso"] not in SEPARADAS])
        if not itens:
            continue
        li = "".join(f'<li id="ref-{r["id"]}"><span class="ref-texto">{_html(partes(r))}</span> <small class="ref-uso">{linha_uso(r, True)}</small></li>' for r in itens)
        out.append(f'<details class="ref-cat" id="ref-cat-{n}"><summary>{n}. {html.escape(nome)} <span class="ref-n">({len(itens)})</span></summary><ol>{li}</ol></details>')
    av = ordenar([r for r in refs if r["uso"] in SEPARADAS])
    if av:
        li = "".join(f'<li id="ref-{r["id"]}"><span class="ref-texto">{_html(partes(r))}</span> <small class="ref-uso">{linha_uso(r, True)}</small></li>' for r in av)
        out.append(f'<details class="ref-cat" id="ref-cat-avaliadas"><summary>Tecnologias avaliadas, não utilizadas, e planejadas <span class="ref-n">({len(av)})</span></summary><ol>{li}</ol></details>')
    return "\n".join(out)


def documento_md(refs: list[dict]) -> str:
    n_cit = len(refs)
    L = ["# Referências bibliográficas", "",
         "Documento **gerado** por `tools/gerar_referencias.py` a partir de `config/referencias.yaml`; não edite à mão. A mesma lista aparece na seção \"Referências bibliográficas\" da landing. "
         f"Total: {n_cit} referências. Data de acesso: 26 nov. 2026 (dia em que cada endereço foi consultado).", "",
         "## Normalização", "",
         "- **Normas.** Estrutura de referência da ABNT NBR 6023 e sistema autor-data de citação da ABNT NBR 10520. **A edição vigente de cada norma não pôde ser confirmada** nesta revisão (o catálogo da ABNT exige consulta interativa e as normas são pagas; as pesquisas automatizadas não retornaram a edição). A NBR 14724 (trabalhos acadêmicos) também não foi consultada. A forma adotada reúne o que é comum às edições conhecidas e **precisa ser conferida pela autora contra a edição vigente** antes de qualquer entrega formal.",
         "- **Autoria.** Até três autores, todos; mais de três, o primeiro seguido de \"et al.\". Sem autor pessoal, a instituição ou o projeto, em maiúsculas. Datas ausentes aparecem como \"[s. d.]\", locais e editoras ausentes como \"[S. l.]\" e \"[s. n.]\".",
         "- **Software e conjuntos de dados.** Versão utilizada quando conhecida; o DOI de software do Zenodo é o do **conceito** (todas as versões), conferido na API do Zenodo, porque o DOI de uma versão específica nem sempre é a versão usada.",
         "- **Datas de acesso.** Todos os endereços foram consultados em 26 nov. 2026. Os marcados \"[endereço não verificado por acesso automatizado]\" não responderam a robôs (bloqueio do site) e precisam de conferência manual.",
         "- **Licença.** Só aparece quando há texto verificável (página do provedor, registro do Zenodo, PyPI, npm ou GitHub). \"Não identificada\" ou \"a confirmar\" significa exatamente isso: **nenhuma licença foi atribuída por suposição**, e a licença MIT do código do projeto não se estende aos dados de terceiros.",
         "- **Uso.** Cada item diz se foi utilizado, utilizado em experimento, é de uma frente arquivada ou foi apenas avaliado. O inventário completo está em [`inventario_fontes.md`](inventario_fontes.md).", ""]
    for n, nome in CATEGORIAS.items():
        itens = ordenar([r for r in refs if r["cat"] == n and r["uso"] not in SEPARADAS])
        if not itens:
            continue
        L += [f"## {n}. {nome}", ""]
        for r in itens:
            L += [f'<a id="ref-{r["id"]}"></a>{_md(partes(r))}  ', f"*{linha_uso(r, False)}*", ""]
    av = ordenar([r for r in refs if r["uso"] in SEPARADAS])
    if av:
        L += ["## Tecnologias avaliadas, não utilizadas, e planejadas", "", "Aparecem aqui só para registrar a avaliação ou o plano; **não fazem parte da metodologia executada**.", ""]
        for r in av:
            L += [f'<a id="ref-{r["id"]}"></a>{_md(partes(r))}  ', f"*{linha_uso(r, False)}*", ""]
    L += ["## Chaves de citação", "", "Citações no texto (autor-data) e a referência correspondente:", "", "| Citação | Referência |", "|---|---|"]
    for r in sorted(refs, key=lambda r: _sem_acento(citacao(r))):
        L.append(f"| ({citacao(r)}) | [{r['id']}](#ref-{r['id']}) |")
    return "\n".join(L) + "\n"


def main() -> None:
    refs = carregar()
    destino = RAIZ / "docs" / "referencias_bibliograficas.md"
    destino.write_text(documento_md(refs), encoding="utf-8")
    print("gravado:", destino, f"({len(refs)} referências)")


if __name__ == "__main__":
    main()
