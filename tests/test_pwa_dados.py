import json
import shutil
import subprocess
from pathlib import Path

import pytest

DADOS = Path(__file__).parent.parent / "src/flooding_mapping/app/static/pwa/dados.js"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not installed")


def run(body):
    code = f"const D=require({json.dumps(str(DADOS))}); {body}"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_the_default_state_has_no_consent_places_or_trips():
    assert run("console.log(JSON.stringify(D.empty()))") == {"consentimento": False, "lugares": [], "trajetos": []}


def test_places_are_validated_and_coordinates_are_rounded_to_about_a_metre():
    r = run("let s=D.empty(); const a=D.addPlace(s,'  Casa ',-51.2300049,-30.0300049); console.log(JSON.stringify({l:a.state.lugares,e:a.erro||null}))")
    assert r["e"] is None and r["l"][0]["nome"] == "Casa" and r["l"][0]["lon"] == -51.23 and r["l"][0]["lat"] == -30.03
    for args, erro in (("'',-51.2,-30", "nome"), ("'X',10,10", "fora do Rio Grande do Sul"), ("'X','a',-30", "fora do Rio Grande do Sul")):
        assert erro in run(f"console.log(JSON.stringify(D.addPlace(D.empty(),{args}).erro))")


def test_duplicate_names_and_the_place_limit_are_refused():
    assert "Já existe" in run("let s=D.addPlace(D.empty(),'Casa',-51.2,-30).state; console.log(JSON.stringify(D.addPlace(s,'casa',-51.3,-30.1).erro))")
    assert "Limite" in run("let s=D.empty(); for(let i=0;i<D.MAX_PLACES;i++) s=D.addPlace(s,'L'+i,-51.2,-30).state; console.log(JSON.stringify(D.addPlace(s,'extra',-51.2,-30).erro))")


def test_removing_a_place_removes_the_trips_that_use_it():
    r = run("""let s=D.addPlace(D.empty(),'Casa',-51.2,-30).state; s=D.addPlace(s,'Trabalho',-51.1,-30.1).state;
      s=D.addTrip(s,'Ida',s.lugares[0].id,s.lugares[1].id,'carro','07:30').state;
      const n=s.trajetos.length; s=D.removePlace(s,s.lugares[0].id); console.log(JSON.stringify({n:n,t:s.trajetos.length,l:s.lugares.length}))""")
    assert r == {"n": 1, "t": 0, "l": 1}


def test_trips_need_two_different_places_and_a_valid_time():
    base = "let s=D.addPlace(D.empty(),'Casa',-51.2,-30).state; s=D.addPlace(s,'Trabalho',-51.1,-30.1).state; const [a,b]=s.lugares.map(p=>p.id);"
    assert "diferentes" in run(base + "console.log(JSON.stringify(D.addTrip(s,'x',a,a,'carro','07:30').erro))")
    assert "horário" in run(base + "console.log(JSON.stringify(D.addTrip(s,'x',a,b,'carro','25:99').erro))")
    assert run(base + "console.log(JSON.stringify(D.addTrip(s,'x',a,b,'foguete','07:30').state.trajetos[0].modal))") == "carro"


def test_a_blocked_or_corrupted_storage_never_breaks_the_app():
    assert run("const bad={getItem(){throw new Error('blocked')},setItem(){throw new Error('blocked')},removeItem(){throw new Error('blocked')}};"
               "console.log(JSON.stringify({l:D.load(bad),s:D.save(bad,D.empty()),w:D.wipe(bad)}))")["s"] is False
    assert run("console.log(JSON.stringify(D.load({getItem:()=>'{isto não é json'})))") == {"consentimento": False, "lugares": [], "trajetos": []}


def test_whatever_comes_out_of_storage_is_sanitised():
    lixo = {"consentimento": "sim", "lugares": [{"id": "a", "nome": "<img onerror=x>", "lon": -51.2, "lat": -30}, {"id": "b", "nome": "Fora", "lon": 10, "lat": 10},
                                                 {"nome": "sem id", "lon": -51, "lat": -30}, None, 5],
            "trajetos": [{"deId": "a", "paraId": "a", "horario": "07:30", "modal": "carro"}, {"deId": "zzz", "paraId": "a", "horario": "07:30", "modal": "carro"}]}
    s = run(f"console.log(JSON.stringify(D.sanitize({json.dumps(lixo)})))")
    assert s["consentimento"] is False                      # only a literal true counts as consent
    assert [p["id"] for p in s["lugares"]] == ["a"]         # out of the state, no id, null and a number are dropped
    assert s["trajetos"] == []                              # same place at both ends, and an unknown place, are dropped


def test_wipe_removes_everything_and_consent_is_revocable():
    r = run("""const mem={}; const st={getItem:k=>mem[k]||null,setItem:(k,v)=>{mem[k]=v},removeItem:k=>{delete mem[k]}};
      let s=D.setConsent(D.addPlace(D.empty(),'Casa',-51.2,-30).state,true); D.save(st,s);
      const antes=Object.keys(mem).length; const depois=D.wipe(st); console.log(JSON.stringify({antes:antes,restou:Object.keys(mem).length,s:depois,rev:D.setConsent(s,false).consentimento}))""")
    assert r["antes"] == 1 and r["restou"] == 0 and r["s"]["lugares"] == [] and r["rev"] is False


def test_the_next_departure_is_today_if_ahead_and_tomorrow_otherwise():
    r = run("""const now=new Date(2026,10,9,10,0,0);
      const f=h=>D.localField(D.nextDeparture(h,now)); console.log(JSON.stringify([f('17:30'),f('07:30'),f('09:55'),f('10:00')]))""")
    assert r == ["2026-11-09T17:30", "2026-11-10T07:30", "2026-11-09T09:55", "2026-11-09T10:00"]
