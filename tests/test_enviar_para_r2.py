"""Envio ao R2: ensaio por padrão, credenciais só do ambiente, cabeçalhos por objeto, pulo do que já existe e CORS com Range. Nenhuma chamada de rede: o cliente é falso."""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import enviar_para_r2 as e  # noqa: E402
import preparar_para_r2 as prep  # noqa: E402


class Falso:
    def __init__(self, existentes=None):
        self.objetos, self.existentes = {}, existentes or {}

    def head_object(self, Bucket, Key):
        if Key in self.objetos:
            o = self.objetos[Key]
            return {"ContentLength": len(o["Body"]), "CacheControl": o["CacheControl"], "ContentType": o["ContentType"], "ContentEncoding": o.get("ContentEncoding"), "Metadata": o.get("Metadata", {})}
        if Key in self.existentes:
            existente = self.existentes[Key]
            return existente if isinstance(existente, dict) else {"ContentLength": existente}
        err = Exception("404")
        err.response = {"Error": {"Code": "404"}}
        raise err

    def put_object(self, **kw):
        self.objetos[kw["Key"]] = kw


@pytest.fixture
def pasta(tmp_path):
    for nome in ("f3", "dr"):
        (tmp_path / nome / "tiles" / "13" / "1").mkdir(parents=True)
        (tmp_path / nome / "tiles" / "13" / "1" / "2.pbf").write_bytes(b"tile" * 2000)
        (tmp_path / nome / "meta.json").write_text(json.dumps({"versao": 1, "n": nome}))
    r = prep.preparar(tmp_path / "f3", tmp_path / "dr", tmp_path / "out")
    return tmp_path / "out" / r["versao_dos_dados"]


def test_the_plan_prefixes_every_key_with_the_versioned_path_and_carries_the_headers(pasta):
    itens = e.plano(pasta)
    assert itens and all(i["chave"].startswith(pasta.name + "/") for i in itens)
    tile = next(i for i in itens if i["chave"].endswith("fase3/tiles/13/1/2.pbf"))
    assert tile["content_encoding"] == "gzip" and "immutable" in tile["cache_control"] and tile["content_type"] == "application/x-protobuf"
    meta = next(i for i in itens if i["chave"].endswith("fase3/meta.json"))
    assert "immutable" not in meta["cache_control"]


def test_upload_sends_each_object_with_its_headers_skips_the_existing_and_verifies(pasta):
    itens = e.plano(pasta)
    primeiro = itens[0]
    cli = Falso(existentes={primeiro["chave"]: {
        "ContentLength": primeiro["bytes"],
        "Metadata": {"sha256": primeiro["sha256"]},
        "ContentType": primeiro["content_type"],
        "ContentEncoding": primeiro["content_encoding"],
        "CacheControl": primeiro["cache_control"],
    }})
    r = e.enviar(cli, "bucket", itens)
    assert r == {"enviados": len(itens) - 1, "pulados": 1} and itens[0]["chave"] not in cli.objetos
    tile = cli.objetos[next(i["chave"] for i in itens if i["chave"].endswith("fase3/tiles/13/1/2.pbf"))]
    assert tile["ContentEncoding"] == "gzip" and tile["ContentType"] == "application/x-protobuf" and "immutable" in tile["CacheControl"]
    assert tile["Metadata"]["sha256"]
    assert e.conferir(cli, "bucket", itens[1:]) == []


def test_same_size_object_with_wrong_hash_is_uploaded_again(pasta):
    item = e.plano(pasta)[0]
    cli = Falso(existentes={item["chave"]: {
        "ContentLength": item["bytes"],
        "Metadata": {"sha256": "0" * 64},
        "ContentType": item["content_type"],
        "ContentEncoding": item["content_encoding"],
        "CacheControl": item["cache_control"],
    }})

    resultado = e.enviar(cli, "bucket", [item])

    assert resultado == {"enviados": 1, "pulados": 0}
    assert cli.objetos[item["chave"]]["Metadata"]["sha256"] == item["sha256"]


def test_credentials_come_only_from_the_environment_and_are_required(monkeypatch):
    with pytest.raises(SystemExit) as x:
        e.cliente_do_ambiente({})
    assert "R2_ACCESS_KEY_ID" in str(x.value) and "não são lidas de argumento nem de arquivo" in str(x.value)


def test_cors_allows_range_only_for_plain_https_origins():
    p = e.politica_cors(["https://flooding-mapping-capstone.pages.dev"])["CORSRules"][0]
    assert p["AllowedMethods"] == ["GET", "HEAD"] and {"Range", "If-Range"} <= set(p["AllowedHeaders"]) and {"Content-Range", "Accept-Ranges"} <= set(p["ExposeHeaders"])
    for ruim in ("http://x.org", "https://x.org/caminho", "*"):
        with pytest.raises(SystemExit):
            e.politica_cors([ruim])


def test_the_default_is_a_dry_run_that_sends_nothing(pasta, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["x", str(pasta)])
    monkeypatch.setattr(e, "cliente_do_ambiente", lambda *a, **k: pytest.fail("não deveria tocar a rede nem pedir credencial"))
    e.main()
    assert "ENSAIO: nada foi enviado" in capsys.readouterr().out


def test_the_tool_has_no_secret_in_code_and_no_bucket_creation():
    codigo = (RAIZ / "tools/enviar_para_r2.py").read_text(encoding="utf-8").split('"""')[2]
    for proibido in ("create_bucket", "delete_object", "delete_bucket", "secret_key=", "AKIA"):
        assert proibido not in codigo, proibido


def test_local_validation_checks_version_count_size_and_the_hash_of_the_original_content(pasta):
    r = e.validar_local(pasta, {"versao": pasta.name})
    assert r["erros"] == [] and r["resumo_confere"] and r["objetos"] > 0 and r["versao"] == pasta.name
    assert e.validar_local(pasta, {"objetos": 4923})["erros"]                                  # a quantidade esperada diferente é apontada
    alvo = next(pasta.rglob("2.pbf"))
    alvo.write_bytes(alvo.read_bytes()[:-3] + b"xyz")                                          # corrompe um objeto
    assert any("2.pbf" in x for x in e.validar_local(pasta)["erros"])
