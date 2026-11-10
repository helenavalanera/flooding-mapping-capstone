import json
import shutil
import subprocess
from pathlib import Path

import pytest

LOGIC = Path(__file__).parent.parent / "src/flooding_mapping/app/static/logic.js"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")


def run(expression):
    code = f"const L=require({json.dumps(str(LOGIC))}); console.log(JSON.stringify({expression}))"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_free_text_is_escaped():
    assert run('L.esc("<img src=x onerror=alert(1)> & \\"q\\"")') == "&lt;img src=x onerror=alert(1)&gt; &amp; &quot;q&quot;"
    assert run("L.esc(null)") == ""


def test_a_missing_traffic_value_is_no_data_not_low_traffic():
    assert run("L.vdmColor(null)") == run("L.vdmColor(NaN)") == "#b9bfc3"
    assert run("L.vdmColor(0)") == "#c6dbef" and run("L.vdmColor(30000)") == "#08306b"
    assert run("L.vdmColor(0)") != run("L.vdmColor(null)")


def test_class_colors_and_unknown_classes():
    assert run('L.classColor("alto")') == "#b3202a"
    assert run('L.classColor("baixo")') != run("L.NO_DATA") and run("L.classColor(null)") == run("L.NO_DATA")


def test_class_at_a_horizon_and_missing_municipality():
    muni = {"dias": [{"horizonte_dias": 0, "classe": "baixo"}, {"horizonte_dias": 2, "classe": "alto"}]}
    assert run(f"L.classAt({json.dumps(muni)}, 2)") == "alto"
    assert run(f"L.classAt({json.dumps(muni)}, 1)") is None and run("L.classAt(undefined, 0)") is None


def test_instants_are_shown_in_brasilia_time():
    assert run('L.formatInstant("2026-11-08T20:42:00Z")') == "08/11/2026 17:42"
    assert run('L.formatInstant("lixo")') == "indisponível"


def test_labels_for_days_blockages_and_probabilities():
    assert run('L.dayLabel(1, "2026-11-09")') == "Amanhã (09/11)"
    assert run('L.blockageSpan({km: 5, km_fim: 7})') == "km 5 a 7" and run('L.blockageSpan({km: 149, km_fim: null})') == "km 149"
    assert run("L.percent(0.0004)") == "<0,1%" and run("L.percent(0.0239)") == "2,4%" and run("L.percent(null)") == "—"


def test_the_four_kinds_of_data_have_distinct_labels_and_classes():
    kinds = run("['observado','previsto','simulado','confirmado'].map(k => L.kind(k))")
    assert len({k["label"] for k in kinds}) == 4 and len({k["cls"] for k in kinds}) == 4
    assert run('L.kind("inventado").cls') == "k-nenhum"
    assert "k-previsto" in run('L.kindBadge("previsto")') and "<script" not in run('L.kindBadge("<script>")')


def test_times_and_amounts_are_formatted_in_portuguese_and_brasilia_time():
    assert run('L.hhmm("2026-11-09T17:30:00-03:00")') == "17:30" and run('L.hhmm("2026-11-09T20:30:00Z")') == "17:30"
    assert run("L.hhmm('lixo')") == "—"
    assert run("L.minutes(32)") == "32 min" and run("L.minutes(65)") == "1 h 05" and run("L.minutes(null)") == "—"
    assert run("L.extraMinutes(6)") == "+6 min" and run("L.extraMinutes(-3)") == "−3 min" and run("L.extraMinutes(0)") == "mesmo tempo"
    assert run("L.mm(0.74)") == "0,7 mm" and run("L.km(null)") == "—"


def test_streets_are_grouped_by_name_with_the_worst_class_first():
    feats = [{"properties": {"nome": "Av. A", "classe": "atencao", "km": 0.4, "escore": 0.2}},
             {"properties": {"nome": "Av. A", "classe": "alto", "km": 0.6, "escore": 0.5}},
             {"properties": {"nome": None, "classe": "atencao", "km": 1.0, "escore": 0.3}},
             {"properties": {"nome": "Rua B", "classe": "atencao", "km": 0.2, "escore": 0.25}}]
    grupos = run(f"L.groupStreets({json.dumps(feats)})")
    assert [g["nome"] for g in grupos] == ["Av. A", "(via sem nome)", "Rua B"]
    assert grupos[0] == {"nome": "Av. A", "km": 1.0, "classe": "alto", "n": 2, "escore": 0.5}


def test_bar_heights_ignore_missing_values_and_never_divide_by_zero():
    assert run("L.barHeights([0, 5, 10, null, NaN], 40)") == [0, 20, 40, 0, 0]
    assert run("L.barHeights([0, 0], 40)") == [0, 0] and run("L.barHeights([1, 2], 40, 10)") == [4, 8]
