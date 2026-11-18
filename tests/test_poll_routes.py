"""Tests for Milestone 5 in-app QR poll routes (/vote, /api/poll/*), poll_store, and Cloud Run/teardown dry-runs."""

from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import firestore
from google.cloud.firestore_v1._helpers import ReadAfterWriteError, get_transaction_id
from jsonschema import ValidationError
import pytest

from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    load_pack,
    resolve_phase2_settings,
    validate_bundle,
)
from engine.poll_store import (
    FirestorePollStore,
    InMemoryPollStore,
    PollCapacityError,
    PollValidationError,
    hash_voter_token,
    render_poll_qr_svg,
)
from server.app import create_app


def _make_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    poll_store: Any = None,
    share_token: str | None = "stage-demo-key-123",
    enable_live_poll: str = "true",
    vote_rpm_limit: str = "240",
    public_base_url: str = "",
) -> TestClient:
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "none")
    monkeypatch.setenv("ENABLE_LIVE_POLL", enable_live_poll)
    monkeypatch.setenv("POLL_VOTE_RPM_LIMIT", vote_rpm_limit)
    monkeypatch.setenv("PUBLIC_BASE_URL", public_base_url)
    if share_token is None:
        monkeypatch.delenv("DEMO_SHARE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("DEMO_SHARE_TOKEN", share_token)
    app = create_app(env_file=tmp_path / "nonexistent.env", poll_store=poll_store)
    return TestClient(app)


def test_vote_html_route_and_health_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(tmp_path, monkeypatch)

    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    health = health_res.json()
    assert health["live_poll_enabled"] is True
    assert health["poll_storage_mode"] == "memory"

    vote_res = client.get("/vote")
    assert vote_res.status_code == 200
    assert "text/html" in vote_res.headers["content-type"]
    assert vote_res.headers.get("cache-control") == "no-cache"
    assert 'data-theme="dark"' in vote_res.text
    assert 'content="no-referrer"' in vote_res.text
    assert 'src="js/vote.js"' in vote_res.text


def test_poll_state_is_strictly_spoiler_free_and_respects_kill_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(tmp_path, monkeypatch)

    res = client.get("/api/poll/state?pack_id=meridian_q3_sgd&rung_id=r1_schema")
    assert res.status_code == 200
    assert res.headers.get("cache-control") == "no-store"
    body = res.json()

    assert body["pack_id"] == "meridian_q3_sgd"
    assert body["rung_id"] == "r1_schema"
    assert body["rung_num"] == 1
    assert body["counts"] == {"A": 0, "B": 0, "C": 0, "D": 0}
    assert body["total_votes"] == 0
    assert body["epoch"] == 1
    assert len(body["options"]) == 4
    assert len(body["available_rungs"]) >= 6
    assert body["storage_mode"] == "memory"

    # Zero-spoiler invariant: never expose correct_key or reveal_takeaway
    assert "correct_key" not in body
    assert "reveal_takeaway" not in body
    assert "correct_key" not in res.text
    assert "reveal_takeaway" not in res.text

    # Invalid slug -> 400; unknown pack/rung -> 404
    assert client.get("/api/poll/state?pack_id=../bad").status_code == 400
    assert client.get("/api/poll/state?pack_id=missing_pack").status_code == 404
    assert client.get("/api/poll/state?pack_id=meridian_q3_sgd&rung_id=r99_missing").status_code == 404

    disabled_client = _make_client(tmp_path, monkeypatch, enable_live_poll="false")
    assert disabled_client.get("/api/poll/state").status_code == 503


def test_poll_vote_dedup_switching_validation_and_capacity_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPollStore(max_voters_per_epoch=2)
    client = _make_client(tmp_path, monkeypatch, poll_store=store)

    voter1 = "voter_token_alpha_0001"
    voter2 = "voter_token_bravo_0002"
    voter3 = "voter_token_charlie_03"

    # Initial vote by voter1 -> A
    r1 = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "A",
            "voter_token": voter1,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["counts"] == {"A": 1, "B": 0, "C": 0, "D": 0}
    assert r1.json()["total_votes"] == 1

    # Idempotent retry -> still 1 vote
    r1_retry = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "A",
            "voter_token": voter1,
        },
    )
    assert r1_retry.status_code == 200
    assert r1_retry.json()["total_votes"] == 1

    # Switch vote A -> B by voter1 -> still 1 total vote, B=1, A=0
    r1_switch = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "B",
            "voter_token": voter1,
        },
    )
    assert r1_switch.status_code == 200
    assert r1_switch.json()["recorded_choice"] == "B"
    assert r1_switch.json()["counts"] == {"A": 0, "B": 1, "C": 0, "D": 0}
    assert r1_switch.json()["total_votes"] == 1

    # Second voter fills capacity (2/2)
    r2 = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "C",
            "voter_token": voter2,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["total_votes"] == 2

    # Net-new 3rd voter blocked with 429 capacity error
    r3 = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "D",
            "voter_token": voter3,
        },
    )
    assert r3.status_code == 429

    # Existing voter1 can STILL switch B -> D even at 2/2 capacity
    r1_switch_full = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "D",
            "voter_token": voter1,
        },
    )
    assert r1_switch_full.status_code == 200
    assert r1_switch_full.json()["counts"] == {"A": 0, "B": 0, "C": 1, "D": 1}
    assert r1_switch_full.json()["total_votes"] == 2

    # Invalid voter_token / choice / extra field -> 400
    assert (
        client.post(
            "/api/poll/vote",
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "A",
                "voter_token": "short",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/poll/vote",
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "Z",
                "voter_token": voter1,
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/poll/vote",
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "A",
                "voter_token": voter1,
                "extra": "nope",
            },
        ).status_code
        == 400
    )


def test_poll_vote_rate_limits_nat_safe_ip_and_per_voter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # High IP limit (shared hotel NAT) + per-voter limit = 15/min
    client = _make_client(tmp_path, monkeypatch, vote_rpm_limit="240")
    voter = "voter_rate_limit_probe_1"

    for i in range(15):
        res = client.post(
            "/api/poll/vote",
            headers={"X-Forwarded-For": "198.51.100.77"},
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r2_glossary",
                "choice": "A" if i % 2 == 0 else "B",
                "voter_token": voter,
            },
        )
        assert res.status_code == 200

    # 16th update from same voter within 60s hits per-voter limit -> 429
    throttled_voter = client.post(
        "/api/poll/vote",
        headers={"X-Forwarded-For": "198.51.100.77"},
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r2_glossary",
            "choice": "C",
            "voter_token": voter,
        },
    )
    assert throttled_voter.status_code == 429

    # Different executive behind the SAME shared NAT IP can still vote!
    other_exec = client.post(
        "/api/poll/vote",
        headers={"X-Forwarded-For": "198.51.100.77"},
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r2_glossary",
            "choice": "B",
            "voter_token": "voter_other_exec_token_2",
        },
    )
    assert other_exec.status_code == 200

    # Explicit IP limit check
    tight_client = _make_client(tmp_path, monkeypatch, vote_rpm_limit="2")
    for idx in range(2):
        ok = tight_client.post(
            "/api/poll/vote",
            headers={"X-Forwarded-For": "10.0.0.1, 203.0.113.55"},
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "B",
                "voter_token": f"voter_ip_limit_token_{idx:02d}",
            },
        )
        assert ok.status_code == 200
    ip_blocked = tight_client.post(
        "/api/poll/vote",
        headers={"X-Forwarded-For": "192.0.2.8, 203.0.113.55"},
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "B",
            "voter_token": "voter_ip_limit_token_99",
        },
    )
    assert ip_blocked.status_code == 429


def test_poll_reset_and_sync_stage_auth_gates_and_epoch_increment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing server token -> fail-closed 503
    unconfigured = _make_client(tmp_path, monkeypatch, share_token=None)
    assert (
        unconfigured.post(
            "/api/poll/reset",
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema"},
        ).status_code
        == 503
    )
    assert (
        unconfigured.post(
            "/api/poll/sync-stage",
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r3_metrics"},
        ).status_code
        == 503
    )

    client = _make_client(tmp_path, monkeypatch, share_token="presenter-secret-999")

    # Unauthenticated / wrong token -> 401
    assert (
        client.post(
            "/api/poll/reset",
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/poll/sync-stage",
            headers={"X-Demo-Key": "wrong-key"},
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r3_metrics"},
        ).status_code
        == 401
    )

    # Authenticated sync-stage -> updates default /api/poll/state rung
    sync_res = client.post(
        "/api/poll/sync-stage",
        headers={"X-Demo-Key": "presenter-secret-999"},
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r3_metrics"},
    )
    assert sync_res.status_code == 200
    assert sync_res.json() == {
        "pack_id": "meridian_q3_sgd",
        "active_stage_rung_id": "r3_metrics",
    }

    default_state = client.get("/api/poll/state?pack_id=meridian_q3_sgd")
    assert default_state.status_code == 200
    assert default_state.json()["rung_id"] == "r3_metrics"
    assert default_state.json()["active_stage_rung_id"] == "r3_metrics"

    # Cast vote, then authenticated reset -> increments epoch & zeros counts
    voter = "voter_reset_epoch_probe_1"
    v_res = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r3_metrics",
            "choice": "B",
            "voter_token": voter,
        },
    )
    assert v_res.status_code == 200
    assert v_res.json()["total_votes"] == 1

    reset_res = client.post(
        "/api/poll/reset",
        headers={"X-Demo-Key": "presenter-secret-999"},
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r3_metrics"},
    )
    assert reset_res.status_code == 200
    reset_body = reset_res.json()
    assert reset_body["epoch"] == 2
    assert reset_body["total_votes"] == 0
    assert reset_body["counts"] == {"A": 0, "B": 0, "C": 0, "D": 0}

    # Same voter can vote again in Epoch 2
    v2_res = client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r3_metrics",
            "choice": "C",
            "voter_token": voter,
        },
    )
    assert v2_res.status_code == 200
    assert v2_res.json()["epoch"] == 2
    assert v2_res.json()["counts"] == {"A": 0, "B": 0, "C": 1, "D": 0}


def test_poll_qr_svg_validation_and_anti_phishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _make_client(tmp_path, monkeypatch)

    ok = client.get(
        "/api/poll/qr.svg?pack_id=meridian_q3_sgd&rung_id=r1_schema",
        headers={"Host": "demo.example.org", "X-Forwarded-Proto": "https"},
    )
    assert ok.status_code == 200
    assert "image/svg+xml" in ok.headers["content-type"]
    assert ok.text.lstrip().startswith("<svg")

    # Bad slug -> 400; unknown pack/rung -> 404
    assert client.get("/api/poll/qr.svg?pack_id=BAD-SLUG").status_code == 400
    assert client.get("/api/poll/qr.svg?pack_id=unknown_pack").status_code == 404
    assert client.get("/api/poll/qr.svg?pack_id=meridian_q3_sgd&rung_id=r99_missing").status_code == 404

    # Host-header injection blocked -> 400
    bad_host = client.get(
        "/api/poll/qr.svg?pack_id=meridian_q3_sgd",
        headers={"Host": "evil.example.com/phish?x=1"},
    )
    assert bad_host.status_code == 400

    # PUBLIC_BASE_URL override works cleanly
    pub_client = _make_client(
        tmp_path,
        monkeypatch,
        public_base_url="https://poll.example.org",
    )
    pub_ok = pub_client.get("/api/poll/qr.svg?pack_id=meridian_q3_sgd")
    assert pub_ok.status_code == 200
    assert "<svg" in pub_ok.text

    # Direct QR helper rejects unsafe schemes
    with pytest.raises(PollValidationError):
        render_poll_qr_svg("javascript:alert(1)")
    with pytest.raises(PollValidationError):
        render_poll_qr_svg("https://example.org/" + "a" * 520)


def test_schema_external_poll_url_and_phase2_poll_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = load_pack("meridian_q3_sgd")
    bundle_copy = copy.deepcopy(bundle)
    bundle_copy["rungs"][0]["poll"]["external_poll_url"] = "https://example.org/polls/r1"
    validate_bundle(bundle_copy)

    bad_bundle = copy.deepcopy(bundle)
    bad_bundle["rungs"][0]["poll"]["external_poll_url"] = "http://insecure.example.org/poll"
    with pytest.raises(ValidationError):
        validate_bundle(bad_bundle)

    # FIRESTORE_DATABASE_ID defaults to <prefix>-polls when unset
    monkeypatch.delenv("FIRESTORE_DATABASE_ID", raising=False)
    monkeypatch.setenv("PACK_ID", "meridian_q3_sgd")
    settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=tmp_path / "nonexistent.env")
    assert settings["FIRESTORE_DATABASE_ID"] == "meridian-polls"
    assert settings["ENABLE_LIVE_POLL"] == "true"
    assert settings["POLL_VOTE_RPM_LIMIT"] == "240"

    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "custom-polls-db")
    custom_settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=tmp_path / "nonexistent.env")
    assert custom_settings["FIRESTORE_DATABASE_ID"] == "custom-polls-db"


class _FakeDocSnap:
    def __init__(self, doc_id: str, data: dict[str, Any] | None, ref: Any) -> None:
        self.id = doc_id
        self._data = copy.deepcopy(data) if data is not None else None
        self.exists = data is not None
        self.reference = ref

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data)


class _FakeQuery:
    def __init__(self, docs: dict[str, dict[str, Any]], col_ref: Any, op: str, val: Any, limit_n: int | None = None) -> None:
        self._docs = docs
        self._col_ref = col_ref
        self._op = op
        self._val = val
        self._limit_n = limit_n

    def limit(self, n: int) -> _FakeQuery:
        return _FakeQuery(self._docs, self._col_ref, self._op, self._val, n)

    def stream(self, transaction: Any = None) -> list[_FakeDocSnap]:
        if transaction is not None and getattr(transaction, "_has_written", False):
            raise ReadAfterWriteError("Attempted read after write in a transaction.")
        matched: list[_FakeDocSnap] = []
        for doc_id, data in sorted(self._docs.items()):
            epoch_val = data.get("epoch")
            if self._op == "==" and epoch_val == self._val:
                matched.append(_FakeDocSnap(doc_id, data, self._col_ref.document(doc_id)))
            elif self._op == "<" and epoch_val < self._val:
                matched.append(_FakeDocSnap(doc_id, data, self._col_ref.document(doc_id)))
        if self._limit_n is not None:
            return matched[: self._limit_n]
        return matched


class _FakeCollectionRef:
    def __init__(self, docs: dict[str, dict[str, Any]], subcollections: dict[str, dict[str, Any]]) -> None:
        self._docs = docs
        self._subcollections = subcollections

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(doc_id, self._docs, self._subcollections)

    def where(self, *, filter: Any) -> _FakeQuery:
        return _FakeQuery(self._docs, self, filter.op_string, filter.value)


class _FakeDocRef:
    def __init__(
        self,
        doc_id: str,
        docs: dict[str, dict[str, Any]],
        subcollections: dict[str, dict[str, Any]],
    ) -> None:
        self.id = doc_id
        self._docs = docs
        self._subcollections = subcollections

    def collection(self, name: str) -> _FakeCollectionRef:
        doc_subs = self._subcollections.setdefault(self.id, {})
        col_docs = doc_subs.setdefault(name, {})
        col_subs = doc_subs.setdefault(f"__subs__{name}", {})
        return _FakeCollectionRef(col_docs, col_subs)

    def get(self, transaction: Any = None) -> _FakeDocSnap:
        if transaction is not None and getattr(transaction, "_has_written", False):
            raise ReadAfterWriteError("Attempted read after write in a transaction.")
        return _FakeDocSnap(self.id, self._docs.get(self.id), self)

    def set(self, data: dict[str, Any]) -> None:
        self._docs[self.id] = copy.deepcopy(data)


class _FakeTransaction:
    def __init__(self) -> None:
        self._max_attempts = 1
        self._read_only = False
        self._id = b"fake-txn"
        self._has_written = False
        self._pending_writes: list[tuple[_FakeDocRef, dict[str, Any]]] = []

    def _begin(self, retry_id: Any = None) -> None:
        del retry_id
        self._has_written = False
        self._pending_writes.clear()

    def _clean_up(self) -> None:
        pass

    def _commit(self) -> None:
        for doc_ref, data in self._pending_writes:
            doc_ref.set(data)
        self._pending_writes.clear()

    def _rollback(self) -> None:
        self._pending_writes.clear()
        self._has_written = False

    def set(self, doc_ref: _FakeDocRef, data: dict[str, Any]) -> None:
        self._has_written = True
        self._pending_writes.append((doc_ref, copy.deepcopy(data)))


class _FakeWriteBatch:
    def __init__(self) -> None:
        self._deletes: list[_FakeDocRef] = []

    def delete(self, doc_ref: _FakeDocRef) -> None:
        self._deletes.append(doc_ref)

    def commit(self) -> None:
        for ref in self._deletes:
            ref._docs.pop(ref.id, None)


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, Any]] = {}
        self.subcollections: dict[str, dict[str, Any]] = {}
        self.get_calls = 0

    def collection(self, name: str) -> _FakeCollectionRef:
        col_docs = self.collections.setdefault(name, {})
        col_subs = self.subcollections.setdefault(name, {})
        outer = self

        class _TrackedCollection(_FakeCollectionRef):
            def document(self, doc_id: str) -> _FakeDocRef:
                ref = super().document(doc_id)
                orig_get = ref.get

                def _counted_get(transaction: Any = None) -> _FakeDocSnap:
                    if transaction is None:
                        outer.get_calls += 1
                    return orig_get(transaction=transaction)

                ref.get = _counted_get  # type: ignore[method-assign]
                return ref

        return _TrackedCollection(col_docs, col_subs)

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    def batch(self) -> _FakeWriteBatch:
        return _FakeWriteBatch()


def test_firestore_poll_store_cache_hash_and_epoch_reset() -> None:
    fake_client = _FakeFirestoreClient()
    store = FirestorePollStore(
        "example-project-id",
        "example-polls",
        client=fake_client,
        cache_ttl_s=60.0,
        max_voters_per_epoch=2,
    )
    assert store.storage_mode == "firestore"

    raw_token = "exec_mobile_token_123456"
    expected_hash = hash_voter_token("meridian_q3_sgd", "r1_schema", 1, raw_token)
    assert raw_token not in expected_hash

    res1 = store.cast_vote("meridian_q3_sgd", "r1_schema", "A", raw_token)
    assert res1["counts"] == {"A": 1, "B": 0, "C": 0, "D": 0}

    # Verify ballot doc stores only hashed doc ID, zero raw voter_token
    ballots = fake_client.subcollections["poll_sessions"]["meridian_q3_sgd__r1_schema"]["ballots"]
    assert f"e1_{expected_hash}" in ballots
    assert all(raw_token not in k for k in ballots)

    # Read cache suppresses duplicate Firestore session gets
    calls_before = fake_client.get_calls
    cached = store.get_poll_tally("meridian_q3_sgd", "r1_schema")
    assert cached["total_votes"] == 1
    assert fake_client.get_calls == calls_before

    # Switch vote A -> B
    res2 = store.cast_vote("meridian_q3_sgd", "r1_schema", "B", raw_token)
    assert res2["counts"] == {"A": 0, "B": 1, "C": 0, "D": 0}
    assert res2["total_votes"] == 1

    # Second voter fills cap; third rejected
    store.cast_vote("meridian_q3_sgd", "r1_schema", "C", "exec_mobile_token_234567")
    with pytest.raises(PollCapacityError):
        store.cast_vote("meridian_q3_sgd", "r1_schema", "D", "exec_mobile_token_345678")

    # Reset increments epoch and deletes prior ballots
    reset = store.reset_poll("meridian_q3_sgd", "r1_schema")
    assert reset["epoch"] == 2
    assert reset["total_votes"] == 0
    assert ballots == {}

    # Stage sync
    assert store.set_active_stage_rung("meridian_q3_sgd", "r4_trust_access") == "r4_trust_access"
    assert store.get_active_stage_rung("meridian_q3_sgd") == "r4_trust_access"


def test_deploy_and_teardown_dry_run_include_firestore_poll_plan() -> None:
    deploy_script = DEFAULT_REPO_ROOT / "scripts" / "deploy_cloud_run.sh"
    res = subprocess.run(
        ["bash", str(deploy_script), "--dry-run"],
        cwd=DEFAULT_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "Firestore Native 'meridian-polls'" in res.stdout
    assert "roles/datastore.user" in res.stdout
    assert "ENABLE_LIVE_POLL=" in res.stdout
    assert "POLL_VOTE_RPM_LIMIT=" in res.stdout

    teardown_script = DEFAULT_REPO_ROOT / "scripts" / "teardown_pack.sh"
    res_td = subprocess.run(
        ["bash", str(teardown_script), "--dry-run", "--delete-cloud-run", "--delete-poll-db"],
        cwd=DEFAULT_REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "PROJECT_ID": "example-sandbox-123", "DATASET_ID": "meridian_commerce"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_td.returncode == 0, res_td.stderr
    assert "datastore.user" in res_td.stdout
    assert "Firestore Native poll database 'meridian-polls'" in res_td.stdout


def test_vote_page_and_stage_poll_ui_contracts() -> None:
    web_dir = DEFAULT_REPO_ROOT / "web"
    vote_html = (web_dir / "vote.html").read_text(encoding="utf-8")
    vote_js = (web_dir / "js" / "vote.js").read_text(encoding="utf-8")
    app_js = (web_dir / "js" / "app.js").read_text(encoding="utf-8")
    styles_css = (web_dir / "css" / "styles.css").read_text(encoding="utf-8")

    assert 'content="no-referrer"' in vote_html
    assert 'data-theme="dark"' in vote_html
    assert 'src="js/vote.js"' in vote_html

    for js_src in (vote_js, app_js):
        assert "innerHTML" not in js_src
        assert "outerHTML" not in js_src
        assert "insertAdjacentHTML" not in js_src
        assert "document.write" not in js_src

    assert "context_poll_voter_token" in vote_js
    assert "/api/poll/state" in vote_js
    assert "/api/poll/vote" in vote_js
    assert "Live on Stage:" in vote_js

    assert "/api/poll/qr.svg" in app_js
    assert "/api/poll/reset" in app_js
    assert "/api/poll/sync-stage" in app_js
    assert "Clear Room Votes" in app_js
    assert "Confirm Clear?" in app_js
    assert "patchPollModalInPlace" in app_js
    assert "pendingPollReset" in app_js
    assert "patchVoteDomInPlace" in vote_js
    assert "activeFetchSeq" in vote_js
    assert "MAX_POLL_BACKOFF_MS" in vote_js
    assert "Math.random" not in vote_js

    assert "min-height: 56px" in styles_css
    assert ".poll-qr-aside" in styles_css
    assert ".poll-option-bar" in styles_css
    assert ".vote-stale-banner" in styles_css


def test_b1_real_firestore_transaction_read_before_write_on_empty_db() -> None:
    """Regression test against real google.cloud.firestore.Transaction._write_pbs ordering."""
    real_client = firestore.Client(
        project="example-project-id",
        database="example-polls",
        credentials=AnonymousCredentials(),
    )
    backing_docs: dict[str, dict[str, Any]] = {}
    backing_subs: dict[str, dict[str, Any]] = {}
    root_col = _FakeCollectionRef(backing_docs, backing_subs)

    class _RealTxnProxyDoc(_FakeDocRef):
        def __init__(
            self,
            doc_id: str,
            docs: dict[str, dict[str, Any]],
            subcollections: dict[str, dict[str, Any]],
            real_ref: Any,
        ) -> None:
            super().__init__(doc_id, docs, subcollections)
            self._real_ref = real_ref

        @property
        def _document_path(self) -> str:
            return self._real_ref._document_path

        @property
        def _client(self) -> Any:
            return self._real_ref._client

        def get(self, transaction: Any = None) -> _FakeDocSnap:
            if transaction is not None:
                get_transaction_id(transaction)
            return super().get(transaction=transaction)

        def collection(self, name: str) -> Any:
            doc_subs = self._subcollections.setdefault(self.id, {})
            col_docs = doc_subs.setdefault(name, {})
            col_subs = doc_subs.setdefault(f"__subs__{name}", {})
            return _RealTxnProxyCollection(col_docs, col_subs, self._real_ref.collection(name))

    class _RealTxnProxyQuery(_FakeQuery):
        def limit(self, n: int) -> _RealTxnProxyQuery:
            return _RealTxnProxyQuery(self._docs, self._col_ref, self._op, self._val, n)

        def stream(self, transaction: Any = None) -> list[_FakeDocSnap]:
            if transaction is not None:
                get_transaction_id(transaction)
            return super().stream(transaction=None)

    class _RealTxnProxyCollection(_FakeCollectionRef):
        def __init__(
            self,
            docs: dict[str, dict[str, Any]],
            subcollections: dict[str, dict[str, Any]],
            real_col: Any,
        ) -> None:
            super().__init__(docs, subcollections)
            self._real_col = real_col

        def document(self, doc_id: str) -> _RealTxnProxyDoc:
            return _RealTxnProxyDoc(
                doc_id,
                self._docs,
                self._subcollections,
                self._real_col.document(doc_id),
            )

        def where(self, *, filter: Any) -> _RealTxnProxyQuery:
            return _RealTxnProxyQuery(self._docs, self, filter.op_string, filter.value)

    class _RealTxnProxyClient:
        def __init__(self) -> None:
            self._cols: dict[str, _RealTxnProxyCollection] = {}

        def collection(self, name: str) -> Any:
            if name not in self._cols:
                self._cols[name] = _RealTxnProxyCollection(
                    root_col._docs,
                    root_col._subcollections,
                    real_client.collection(name),
                )
            return self._cols[name]

        def transaction(self) -> firestore.Transaction:
            txn = real_client.transaction(max_attempts=1)
            real_doc = real_client.collection("poll_sessions").document("meridian_q3_sgd__r1_schema")

            def _fake_begin(retry_id: Any = None) -> None:
                del retry_id
                txn._id = b"real-sdk-txn-1"

            def _fake_commit() -> list[Any]:
                # Replay buffered writes into in-memory backing store
                for pb in txn._write_pbs:
                    path = pb.update.name
                    if "/ballots/" in path:
                        doc_id = path.rsplit("/ballots/", 1)[-1]
                        ballots = backing_subs.setdefault("meridian_q3_sgd__r1_schema", {}).setdefault("ballots", {})
                        ballots[doc_id] = {
                            "choice": pb.update.fields["choice"].string_value,
                            "epoch": int(pb.update.fields["epoch"].integer_value),
                        }
                    elif "/poll_sessions/" in path:
                        doc_id = path.rsplit("/poll_sessions/", 1)[-1]
                        backing_docs[doc_id] = {
                            "epoch": int(pb.update.fields["epoch"].integer_value),
                        }
                txn._write_pbs = []
                txn._id = None
                return []

            def _fake_rollback() -> None:
                txn._write_pbs = []
                txn._id = None

            txn._begin = _fake_begin  # type: ignore[method-assign]
            txn._commit = _fake_commit  # type: ignore[method-assign]
            txn._rollback = _fake_rollback  # type: ignore[method-assign]
            del real_doc
            return txn

    proxy_client = _RealTxnProxyClient()
    store = FirestorePollStore("example-project-id", "example-polls", client=proxy_client)
    res = store.cast_vote("meridian_q3_sgd", "r1_schema", "B", "exec_real_txn_token_001")
    assert res["recorded_choice"] == "B"
    assert res["recorded_epoch"] == 1
    assert res["counts"] == {"A": 0, "B": 1, "C": 0, "D": 0}
    assert res["total_votes"] == 1


def test_h1_pack_poll_cache_and_single_flight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_mod = sys.modules["server.app"]

    load_calls = 0
    orig_load = app_mod.load_raw_pack

    def _counting_load(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal load_calls
        load_calls += 1
        return orig_load(*args, **kwargs)

    monkeypatch.setattr(app_mod, "load_raw_pack", _counting_load)
    client = _make_client(tmp_path, monkeypatch)

    for _ in range(5):
        assert client.get("/api/poll/state?pack_id=meridian_q3_sgd&rung_id=r1_schema").status_code == 200
        assert (
            client.get(
                "/api/poll/qr.svg?pack_id=meridian_q3_sgd&rung_id=r1_schema",
                headers={"Host": "demo.example.org", "X-Forwarded-Proto": "https"},
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/poll/vote",
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "A",
                "voter_token": "cache_test_voter_token_1",
            },
        ).status_code
        == 200
    )
    assert load_calls == 1

    # Single-flight lock on FirestorePollStore.get_poll_tally
    fake_client = _FakeFirestoreClient()
    orig_collection = fake_client.collection

    def _slow_collection(name: str) -> Any:
        col = orig_collection(name)
        orig_doc = col.document

        def _slow_doc(doc_id: str) -> Any:
            doc = orig_doc(doc_id)
            orig_get = doc.get

            def _delayed_get(transaction: Any = None) -> Any:
                if transaction is None:
                    time.sleep(0.05)
                return orig_get(transaction=transaction)

            doc.get = _delayed_get  # type: ignore[method-assign]
            return doc

        col.document = _slow_doc  # type: ignore[method-assign]
        return col

    fake_client.collection = _slow_collection  # type: ignore[method-assign]
    sf_store = FirestorePollStore("example-project-id", "example-polls", client=fake_client, cache_ttl_s=60.0)
    results: list[dict[str, Any]] = []
    threads = [
        threading.Thread(target=lambda: results.append(sf_store.get_poll_tally("meridian_q3_sgd", "r1_schema")))
        for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 6
    assert fake_client.get_calls == 1


def test_m1_read_rate_limit_default_3000_and_m4_503_mapping_and_nits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLL_READ_RPM_LIMIT", raising=False)
    settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=tmp_path / "nonexistent.env")
    assert settings["POLL_READ_RPM_LIMIT"] == "3000"

    # Tight POLL_READ_RPM_LIMIT enforced cleanly
    monkeypatch.setenv("POLL_READ_RPM_LIMIT", "2")
    limited_client = _make_client(tmp_path, monkeypatch)
    assert limited_client.get("/api/poll/state").status_code == 200
    assert limited_client.get("/api/poll/state").status_code == 200
    assert limited_client.get("/api/poll/state").status_code == 429
    monkeypatch.setenv("POLL_READ_RPM_LIMIT", "3000")

    # /vote/ and /vote.html serve vote.html with Cache-Control: no-cache
    for route in ("/vote", "/vote/", "/vote.html"):
        r = limited_client.get(route)
        assert r.status_code == 200
        assert r.headers.get("cache-control") == "no-cache"

    # Bracketed IPv6 Host allowed on /api/poll/qr.svg; ENABLE_LIVE_POLL=false -> 503
    ipv6_qr = limited_client.get("/api/poll/qr.svg?pack_id=meridian_q3_sgd", headers={"Host": "[::1]:8080"})
    assert ipv6_qr.status_code == 200
    disabled_client = _make_client(tmp_path, monkeypatch, enable_live_poll="false")
    assert disabled_client.get("/api/poll/qr.svg?pack_id=meridian_q3_sgd").status_code == 503

    # K_SERVICE + InMemoryPollStore surfaces poll_storage_warning in /api/health
    monkeypatch.setenv("K_SERVICE", "context-is-all-you-need")
    warn_health = limited_client.get("/api/health").json()
    assert warn_health["poll_storage_warning"] is not None
    monkeypatch.delenv("K_SERVICE", raising=False)

    # M4: GoogleAPIError / DefaultCredentialsError -> clean redacted HTTP 503 (never raw 500)
    class _BrokenClient:
        def __init__(self, exc: Exception) -> None:
            self._exc = exc

        def collection(self, name: str) -> Any:
            del name
            raise self._exc

        def transaction(self) -> Any:
            raise self._exc

    for exc in (ServiceUnavailable("backend down"), DefaultCredentialsError("missing adc")):
        broken_store = FirestorePollStore("example-project-id", "example-polls", client=_BrokenClient(exc))
        broken_client = _make_client(tmp_path, monkeypatch, poll_store=broken_store)
        res_state = broken_client.get("/api/poll/state?pack_id=meridian_q3_sgd&rung_id=r1_schema")
        assert res_state.status_code == 503
        assert "unavailable" in res_state.json()["detail"].lower()

        res_vote = broken_client.post(
            "/api/poll/vote",
            json={
                "pack_id": "meridian_q3_sgd",
                "rung_id": "r1_schema",
                "choice": "A",
                "voter_token": "broken_store_probe_token_1",
            },
        )
        assert res_vote.status_code == 503

        res_reset = broken_client.post(
            "/api/poll/reset",
            headers={"X-Demo-Key": "stage-demo-key-123"},
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema"},
        )
        assert res_reset.status_code == 503

        res_sync = broken_client.post(
            "/api/poll/sync-stage",
            headers={"X-Demo-Key": "stage-demo-key-123"},
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema"},
        )
        assert res_sync.status_code == 503

    # R1: @firestore.transactional retry exhaustion raises plain ValueError -> mapped to clean HTTP 503
    retry_exhausted_store = FirestorePollStore(
        "example-project-id",
        "example-polls",
        client=_BrokenClient(ValueError("Failed to commit transaction in 5 attempts.")),
    )
    retry_exhausted_client = _make_client(tmp_path, monkeypatch, poll_store=retry_exhausted_store)
    res_aborted = retry_exhausted_client.post(
        "/api/poll/vote",
        json={
            "pack_id": "meridian_q3_sgd",
            "rung_id": "r1_schema",
            "choice": "B",
            "voter_token": "aborted_txn_probe_token_1",
        },
    )
    assert res_aborted.status_code == 503
    assert "unavailable" in res_aborted.json()["detail"].lower()


