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
