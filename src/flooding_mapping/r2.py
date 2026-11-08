"""Cloudflare R2 object storage with a hard operation budget.

The R2 free tier covers 10 GB-month, 1 million Class A and 10 million Class B
operations per month (Standard storage only). This module keeps every run well
inside it:

* every request is charged to an :class:`OpBudget` *before* it is sent, and the
  run aborts with :class:`BudgetExceeded` when the budget would be crossed;
* only ``GetObject`` (Class B) and ``PutObject`` (Class A) are used: no listing,
  no ``HeadObject``, no ``CopyObject``, no multipart upload;
* retries are capped, and every attempt is charged, including failed ones;
* boto3's own retry layer is disabled so no request is repeated unseen.

``boto3`` is imported only by :meth:`R2Store.from_env`, so the rest of the
package and the tests do not need it.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

REQUIRED_ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
CONTENT_TYPE = "application/json"


class BudgetExceeded(RuntimeError):
    """Raised before a request that would cross the configured budget."""


@dataclass
class OpBudget:
    """Per-run ceiling for Class A (writes) and Class B (reads) operations."""

    max_class_a: int = 10
    max_class_b: int = 5
    class_a: int = 0
    class_b: int = 0

    def charge(self, kind: str) -> None:
        """Count one operation of ``kind`` ("A" or "B") or raise."""
        if kind == "A":
            if self.class_a + 1 > self.max_class_a:
                raise BudgetExceeded(f"Class A budget of {self.max_class_a} exceeded")
            self.class_a += 1
        elif kind == "B":
            if self.class_b + 1 > self.max_class_b:
                raise BudgetExceeded(f"Class B budget of {self.max_class_b} exceeded")
            self.class_b += 1
        else:
            raise ValueError(f"Unknown operation class: {kind!r}")


def error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None) or {}
    return str(response.get("Error", {}).get("Code", ""))


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None) or {}
    return response.get("ResponseMetadata", {}).get("HTTPStatusCode")


def _is_transient(exc: Exception) -> bool:
    """Connection problems and 5xx answers may succeed on a second try."""
    status = _http_status(exc)
    return status is None or status >= 500


def _dump(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class R2Store:
    """JSON object store over an S3-compatible client, charged to a budget."""

    def __init__(
        self,
        client: Any,
        bucket: str,
        budget: OpBudget | None = None,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.budget = budget or OpBudget()
        self.max_attempts = max_attempts
        self._sleep = sleep

    @classmethod
    def from_env(
        cls, budget: OpBudget | None = None, environ: Mapping[str, str] | None = None
    ) -> "R2Store":
        """Build a store from the R2_* environment variables (never printed)."""
        env = os.environ if environ is None else environ
        missing = [name for name in REQUIRED_ENV if not env.get(name)]
        if missing:
            raise RuntimeError("Missing environment variables: " + ", ".join(missing))
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=env["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                # "max_attempts" would count retries (1 -> 2 attempts); this is the total.
                retries={"total_max_attempts": 1},
                connect_timeout=10,
                read_timeout=30,
            ),
        )
        return cls(client, env["R2_BUCKET"], budget)

    def get_bytes(self, key: str) -> bytes | None:
        """The raw object, or ``None`` when the key does not exist."""
        self.budget.charge("B")
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 - boto3 raises a dynamic ClientError
            if error_code(exc) in {"NoSuchKey", "404"} or _http_status(exc) == 404:
                return None
            raise
        return response["Body"].read()

    def get_json(self, key: str) -> Any | None:
        """Return the decoded object, or ``None`` when the key does not exist."""
        raw = self.get_bytes(key)
        return None if raw is None else json.loads(raw)

    def list_keys(self, prefix: str) -> list[str]:
        """Keys under ``prefix``, one Class A operation per page of 1,000.

        For analysis jobs only: the collector itself never lists the bucket.
        """
        keys: list[str] = []
        token = None
        while True:
            self.budget.charge("A")
            extra = {"ContinuationToken": token} if token else {}
            page = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix, **extra)
            keys += [item["Key"] for item in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                return sorted(keys)
            token = page["NextContinuationToken"]

    def put_bytes(self, key: str, body: bytes, content_type: str = CONTENT_TYPE) -> None:
        """Write the object, retrying only transient failures, within the cap."""
        for attempt in range(1, self.max_attempts + 1):
            self.budget.charge("A")
            try:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)
                return
            except Exception as exc:  # noqa: BLE001
                if attempt == self.max_attempts or not _is_transient(exc):
                    raise
                self._sleep(2**attempt)

    def put_json(self, key: str, obj: Any) -> None:
        self.put_bytes(key, _dump(obj))


class MemoryStore:
    """In-memory stand-in with the same interface and the same accounting."""

    def __init__(self, budget: OpBudget | None = None) -> None:
        self.budget = budget or OpBudget()
        self.objects: dict[str, bytes] = {}

    def get_bytes(self, key: str) -> bytes | None:
        self.budget.charge("B")
        return self.objects.get(key)

    def get_json(self, key: str) -> Any | None:
        raw = self.get_bytes(key)
        return None if raw is None else json.loads(raw)

    def put_bytes(self, key: str, body: bytes, content_type: str = CONTENT_TYPE) -> None:
        self.budget.charge("A")
        self.objects[key] = body

    def put_json(self, key: str, obj: Any) -> None:
        self.put_bytes(key, _dump(obj))

    def list_keys(self, prefix: str) -> list[str]:
        self.budget.charge("A")
        return sorted(k for k in self.objects if k.startswith(prefix))
