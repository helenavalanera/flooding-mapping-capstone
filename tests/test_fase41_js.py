"""Fase 4.1: painel e legenda do inventário de drenagem (drenagem.js), em Node, sem navegador."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "src/flooding_mapping/app/static"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")
PRELUDIO = f"""
global.window = {{ Logic: require({json.dumps(str(STATIC / "logic.js"))}) }};
global.document = {{ getElementById: () => null }};
global.location = {{ href: "http://x/y/" }};
require({json.dumps(str(STATIC / "drenagem.js"))});
const Dr = window.Drenagem;
Dr.meta = {{ tamanho_do_fragmento: 1024, dicionario_de_campos: {{ rede_pluvial: {{ diametro: {{ campo_original: "DIAMETRO", unidade: "mm", origem_da_unidade: "inferida" }}, material: {{ campo_original: "MATERIAL", unidade: null, origem_da_unidade: null }} }},
  pontos: {{}}, casas_de_bomba: {{}} }}, camadas: {{ rede: {{ registros: 135856 }}, pocos: {{ registros: 1 }}, bocas: {{ registros: 1 }}, bombas: {{ registros: 24 }} }} }};
const REDE = {{ id_origem: 10, camada_origem: "rede_pluvial_sem_acesso", diametro: 300, material: null, comprimento_pela_geometria: 12.34, ativo_no_cadastro: 0, usar_no_inventario: true, duplicata_exata_de: null,
  diametro_fora_da_faixa_plausivel: true, data_implantacao_suspeita: false, evidencia_geometrica_ambos_extremos_ligados: false, evidencia_geometrica_inicio_coincide_com_outro_extremo: true }};
"""


def run(expressao):
    r = subprocess.run([node, "-e", PRELUDIO + f"console.log(JSON.stringify({expressao}))"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def test_the_record_panel_shows_category_quality_and_original_attributes_with_explicit_absence():
    h = run('Dr.corpo("rede", REDE)')
    assert "Registro sem acesso" in h and "Registro do cadastro, não funcionamento" in h
    assert "300 mm (unidade inferida)" in h and "12,3 m" in h
    assert "Marcado como ativo no cadastro</dt><dd>não" in h                          # 0 é "não", e não some nem vira "não informado"
    assert "valores sinalizados: diâmetro fora da faixa plausível" in h
    assert "<span class='muted'>não informado</span>" in h and "NaN" not in h and "undefined" not in h and ">null<" not in h   # material nulo: não informado
    assert "Evidência geométrica (não é conexão hidráulica)" in h and "início coincide com o extremo de outra linha: sim" in h
    assert "<th scope='row'>diametro <span class='small'>(DIAMETRO, mm, unidade inferida)</span>" in h                          # nome original e unidade marcada como inferida
    assert h.count("<tr>") == len(json.loads(json.dumps(run("Object.keys(REDE)"))))                                              # todos os atributos na tabela


def test_a_duplicate_is_flagged_and_a_zero_depth_is_not_confused_with_absence():
    h = run('Dr.corpo("pocos", { usar_no_inventario: false, duplicata_exata_de: "55", profundidade: 0, altitude_da_tampa: null })')
    assert "registro duplicado (duplicata exata de <code>55</code>), fora do inventário" in h
    assert "Profundidade</dt><dd>0 (unidade inferida)" in h and "Altitude da tampa</dt><dd><span class='muted'>não informado</span>" in h


def test_a_pump_house_never_invents_a_capacity():
    sem = run('Dr.corpo("bombas", { nome: "CB-2", capacidade_informada: false, capacidade_texto_original: null })')
    assert "Capacidade informada no cadastro</dt><dd><span class='muted'>não informado</span>" in sem


def test_the_legend_distinguishes_existing_no_access_not_connected_duplicate_and_line_from_point():
    h = run("Dr.legenda()")
    for t in ("Cadastro existente", "Registro sem acesso", "Cadastrado como não interligado", "Registro duplicado (fora do inventário)", "Poço de visita", "Boca de lobo", "Casa de bomba", "Ponto duplicado", "nunca como zero"):
        assert t in h, t
    assert h.count("(linha)") == 5 and h.count("(ponto)") == 4
    cores = run("Object.values(Dr.COR)")
    assert len(set(cores)) == len(cores)                                              # uma cor para cada coisa
    assert "dashed" in h and "dotted" in h
    assert "Poço de visita" not in run("(Dr.grupos.pocos = false, Dr.legenda())") and "Cadastro existente" in run("Dr.legenda()")


def test_every_text_stays_within_what_the_cadastre_says():
    texto = json.dumps(run("Dr.textos()"), ensure_ascii=False).lower()
    assert "não indica capacidade de vazão" in texto and "não entra no cálculo" in texto and "não é conexão hidráulica" in texto
    h = (run('Dr.corpo("rede", REDE)') + run("Dr.legenda()")).lower().replace(run("Dr.textos().aviso").lower().replace("&", "&amp;"), "")   # o aviso nega essas afirmações; o resto não as faz
    for termo in ("funcionando", "em funcionamento", "eficiência", "conectividade", "capacidade de vazão", "entupid", "alagad"):
        assert termo not in h, termo
