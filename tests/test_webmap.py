import json
import re

from flooding_mapping.webmap import build_html, embed_json


def test_embedded_json_cannot_close_the_script_element():
    data = {"name": "</script><script>alert(1)</script>", "amp": "a & b"}
    text = embed_json(data)
    assert "<" not in text and ">" not in text and "&" not in text
    assert json.loads(text) == data


def test_html_embeds_data_and_pins_leaflet_version():
    html = build_html({"meta": {"x": "</script>"}})
    assert not re.search(r"__[A-Z_]+__", html)        # every placeholder replaced
    # The embedded basemap is the default; OSM tiles are only an option (they
    # block file:// pages) and no keyed tile provider is used.
    assert '"Base própria (offline)": ownBase' in html and "cartocdn" not in html
    assert "leaflet/1.9.4/leaflet.min.js" in html
    payload = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert json.loads(payload.group(1)) == {"meta": {"x": "</script>"}}
    # External text must never be rendered as HTML.
    assert "innerHTML" not in html


def test_carto_key_makes_carto_the_default_basemap(monkeypatch, tmp_path):
    from flooding_mapping import webmap

    monkeypatch.setattr(webmap, "resolve", lambda rel: tmp_path / rel)
    monkeypatch.delenv("CARTO_API_KEY", raising=False)
    assert webmap.carto_key() is None
    without = webmap.basemap_js(None)
    assert "cartocdn" not in without and "]).addTo(map);\nconst osmTiles" in without

    monkeypatch.setenv("CARTO_API_KEY", " chave-ficticia/123 ")
    key = webmap.carto_key()
    assert key == "chave-ficticia/123"
    script = webmap.basemap_js(key)
    assert "rastertiles/voyager/{z}/{x}/{y}.png?key=chave-ficticia%2F123" in script
    assert '"CARTO Voyager": cartoTiles' in script and "© CARTO" in script
    assert "]);\nconst osmTiles" in script          # embedded base no longer added by default


def test_carto_key_file_is_used_when_env_is_absent(monkeypatch, tmp_path):
    from flooding_mapping import webmap

    monkeypatch.setattr(webmap, "resolve", lambda rel: tmp_path / rel)
    monkeypatch.delenv("CARTO_API_KEY", raising=False)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "carto_api_key.txt").write_text("abc\n")
    assert webmap.carto_key() == "abc"
