import io
import json

import pytest

from flooding_mapping.r2 import BudgetExceeded, MemoryStore, OpBudget, R2Store


class FakeClientError(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}


class FakeClient:
    """Minimal S3 client: scripted failures, then success."""

    def __init__(self, put_failures=(), objects=None):
        self.put_failures = list(put_failures)
        self.objects = dict(objects or {})
        self.put_calls = 0
        self.get_calls = 0

    def put_object(self, Bucket, Key, Body, ContentType):
        self.put_calls += 1
        if self.put_failures:
            raise self.put_failures.pop(0)
        self.objects[Key] = Body

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start:start + 2]  # tiny pages to exercise pagination
        more = start + 2 < len(keys)
        return {"Contents": [{"Key": k} for k in page], "IsTruncated": more,
                **({"NextContinuationToken": str(start + 2)} if more else {})}

    def get_object(self, Bucket, Key):
        self.get_calls += 1
        if Key not in self.objects:
            raise FakeClientError("NoSuchKey", 404)
        return {"Body": io.BytesIO(self.objects[Key])}


def make_store(client, **kwargs):
    return R2Store(client, "bucket", sleep=lambda _: None, **kwargs)


def test_put_then_get_roundtrip_and_counts():
    client = FakeClient()
    store = make_store(client)
    store.put_json("a/b.json", {"x": 1, "texto": "açúcar"})
    assert store.get_json("a/b.json") == {"x": 1, "texto": "açúcar"}
    assert (store.budget.class_a, store.budget.class_b) == (1, 1)


def test_get_missing_key_returns_none_and_is_charged():
    store = make_store(FakeClient())
    assert store.get_json("nope") is None
    assert store.budget.class_b == 1


def test_transient_failure_is_retried_and_every_attempt_is_charged():
    client = FakeClient(put_failures=[FakeClientError("InternalError", 500)] * 2)
    store = make_store(client)
    store.put_json("k", {"ok": True})
    assert client.put_calls == 3
    assert store.budget.class_a == 3


def test_retries_are_capped():
    client = FakeClient(put_failures=[FakeClientError("InternalError", 500)] * 5)
    store = make_store(client, max_attempts=3)
    with pytest.raises(FakeClientError):
        store.put_json("k", {})
    assert client.put_calls == 3
    assert store.budget.class_a == 3


def test_client_errors_are_not_retried():
    client = FakeClient(put_failures=[FakeClientError("AccessDenied", 403)])
    store = make_store(client)
    with pytest.raises(FakeClientError):
        store.put_json("k", {})
    assert client.put_calls == 1


def test_budget_blocks_the_request_before_it_is_sent():
    client = FakeClient()
    store = make_store(client, budget=OpBudget(max_class_a=2, max_class_b=1))
    store.put_json("1", {})
    store.put_json("2", {})
    with pytest.raises(BudgetExceeded):
        store.put_json("3", {})
    assert client.put_calls == 2
    store.get_json("1")
    with pytest.raises(BudgetExceeded):
        store.get_json("2")
    assert client.get_calls == 1


def test_from_env_reports_missing_variables_without_values():
    with pytest.raises(RuntimeError) as error:
        R2Store.from_env(environ={"R2_ACCOUNT_ID": "segredo"})
    message = str(error.value)
    assert "R2_BUCKET" in message and "segredo" not in message


def test_memory_store_matches_the_accounting():
    store = MemoryStore()
    store.put_json("k", {"v": 1})
    assert store.get_json("k") == {"v": 1}
    assert store.get_json("missing") is None
    assert (store.budget.class_a, store.budget.class_b) == (1, 2)
    assert json.loads(store.objects["k"]) == {"v": 1}


def test_boto3_client_does_not_retry_on_its_own():
    """A hidden boto3 retry would escape the budget; skipped where boto3 is absent."""
    pytest.importorskip("boto3")
    store = R2Store.from_env(
        environ={
            "R2_ACCOUNT_ID": "abc123",
            "R2_ACCESS_KEY_ID": "k",
            "R2_SECRET_ACCESS_KEY": "s",
            "R2_BUCKET": "b",
        }
    )
    assert store.client.meta.config.retries["total_max_attempts"] == 1
    assert store.client.meta.endpoint_url == "https://abc123.r2.cloudflarestorage.com"


def test_list_keys_follows_pagination_and_charges_each_page():
    client = FakeClient(objects={f"a/{i}": b"{}" for i in range(5)} | {"b/0": b"{}"})
    store = make_store(client)
    assert store.list_keys("a/") == [f"a/{i}" for i in range(5)]
    assert store.budget.class_a == 3  # 5 keys in pages of 2
