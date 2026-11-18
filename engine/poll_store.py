"""Thread-safe and Firestore-backed live audience poll store + offline SVG QR generator."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import io
import logging
import re
import threading
import time
from typing import Any, Protocol, TypeVar

import segno

__all__ = [
    "DEFAULT_POLL_CACHE_TTL_S",
    "FirestorePollStore",
    "InMemoryPollStore",
    "MAX_VOTERS_PER_EPOCH",
    "PollCapacityError",
    "PollError",
    "PollStore",
    "PollStoreUnavailableError",
    "PollValidationError",
    "VALID_CHOICES",
    "hash_voter_token",
    "render_poll_qr_svg",
    "validate_voter_token",
]

_logger = logging.getLogger(__name__)
_T = TypeVar("_T")

VALID_CHOICES: tuple[str, ...] = ("A", "B", "C", "D")
MAX_VOTERS_PER_EPOCH = 300
DEFAULT_POLL_CACHE_TTL_S = 1.0
_BATCH_DELETE_LIMIT = 400
_ID_SLUG_REGEX = re.compile(r"^[a-z0-9_]{1,64}$")
_VOTER_TOKEN_REGEX = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class PollError(ValueError):
    """Base error for poll storage and validation failures."""


class PollValidationError(PollError):
    """Raised when poll identifiers, choices, voter tokens, or QR URLs are invalid."""


class PollCapacityError(PollError):
    """Raised when an epoch reaches MAX_VOTERS_PER_EPOCH for net-new voters."""


class PollStoreUnavailableError(PollError):
    """Raised when the underlying Firestore backend or credentials are unavailable."""


class PollStore(Protocol):
    """Storage interface implemented by InMemoryPollStore and FirestorePollStore."""

    @property
    def storage_mode(self) -> str: ...

    def get_poll_tally(self, pack_id: str, rung_id: str) -> dict[str, Any]: ...

    def cast_vote(
        self,
        pack_id: str,
        rung_id: str,
        choice: str,
        voter_token: str,
    ) -> dict[str, Any]: ...

    def reset_poll(self, pack_id: str, rung_id: str) -> dict[str, Any]: ...

    def get_active_stage_rung(self, pack_id: str) -> str | None: ...

    def set_active_stage_rung(self, pack_id: str, rung_id: str) -> str: ...


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_slug(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_SLUG_REGEX.match(value):
        raise PollValidationError(f"Invalid {field_name} format: {value!r}")
    return value


def _validate_choice(choice: str) -> str:
    if not isinstance(choice, str) or choice not in VALID_CHOICES:
        raise PollValidationError(f"Invalid choice {choice!r}; must be one of {VALID_CHOICES}.")
    return choice


def validate_voter_token(voter_token: str) -> str:
    """Validates an opaque client voter token without logging or storing raw PII."""
    if not isinstance(voter_token, str) or not _VOTER_TOKEN_REGEX.match(voter_token):
        raise PollValidationError(
            "Invalid voter_token format; expected 16-64 characters matching ^[A-Za-z0-9_-]{16,64}$."
        )
    return voter_token


def hash_voter_token(pack_id: str, rung_id: str, epoch: int, voter_token: str) -> str:
    """Computes a deterministic, unlinkable 32-hex voter hash scoped to pack, rung, and epoch."""
    _validate_slug(pack_id, "pack_id")
    _validate_slug(rung_id, "rung_id")
    if epoch < 1:
        raise PollValidationError(f"Epoch must be >= 1, got {epoch}")
    validate_voter_token(voter_token)
    digest = hashlib.sha256(f"{pack_id}:{rung_id}:e{epoch}:{voter_token}".encode("utf-8")).hexdigest()
    return digest[:32]


def _empty_counts() -> dict[str, int]:
    return {choice: 0 for choice in VALID_CHOICES}


def _copy_tally(tally: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(tally.get("counts") or _empty_counts())
    return {
        "pack_id": str(tally["pack_id"]),
        "rung_id": str(tally["rung_id"]),
        "counts": {choice: int(counts.get(choice, 0)) for choice in VALID_CHOICES},
        "total_votes": int(tally.get("total_votes", 0)),
        "epoch": int(tally.get("epoch", 1)),
        "storage_mode": str(tally.get("storage_mode", "memory")),
    }


def render_poll_qr_svg(vote_url: str) -> str:
    """Generates an inline-safe SVG QR code locally via segno with zero external network calls."""
    if not isinstance(vote_url, str) or not vote_url.startswith(("http://", "https://")):
        raise PollValidationError("vote_url must start with http:// or https://")
    if len(vote_url) > 512:
        raise PollValidationError("vote_url exceeds maximum length of 512 characters")
    if any(ch.isspace() or ord(ch) < 32 for ch in vote_url):
        raise PollValidationError("vote_url must not contain whitespace or control characters")

    qr = segno.make(vote_url, error="m")
    buf = io.BytesIO()
    qr.save(
        buf,
        kind="svg",
        scale=5,
        border=2,
        dark="#0b1220",
        light="#ffffff",
        xmldecl=False,
    )
    return buf.getvalue().decode("utf-8")


class InMemoryPollStore:
    """Thread-safe in-memory poll store for local offline mode and unit tests."""

    def __init__(self, *, max_voters_per_epoch: int = MAX_VOTERS_PER_EPOCH) -> None:
        if max_voters_per_epoch < 1:
            raise ValueError("max_voters_per_epoch must be >= 1")
        self._max_voters_per_epoch = max_voters_per_epoch
        self._lock = threading.Lock()
        self._epochs: dict[tuple[str, str], int] = {}
        self._ballots: dict[tuple[str, str, int], dict[str, str]] = {}
        self._stage_rungs: dict[str, str] = {}

    @property
    def storage_mode(self) -> str:
        return "memory"

    def _compute_tally_locked(self, pack_id: str, rung_id: str, epoch: int) -> dict[str, Any]:
        ballots = self._ballots.get((pack_id, rung_id, epoch), {})
        counts = _empty_counts()
        for choice in ballots.values():
            if choice in counts:
                counts[choice] += 1
        return {
            "pack_id": pack_id,
            "rung_id": rung_id,
            "counts": counts,
            "total_votes": sum(counts.values()),
            "epoch": epoch,
            "storage_mode": self.storage_mode,
        }

    def get_poll_tally(self, pack_id: str, rung_id: str) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")
        with self._lock:
            epoch = self._epochs.get((pack_id, rung_id), 1)
            return self._compute_tally_locked(pack_id, rung_id, epoch)

    def cast_vote(
        self,
        pack_id: str,
        rung_id: str,
        choice: str,
        voter_token: str,
    ) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")
        _validate_choice(choice)
        validate_voter_token(voter_token)

        with self._lock:
            epoch = self._epochs.get((pack_id, rung_id), 1)
            voter_hash = hash_voter_token(pack_id, rung_id, epoch, voter_token)
            ballots = self._ballots.setdefault((pack_id, rung_id, epoch), {})
            if voter_hash not in ballots and len(ballots) >= self._max_voters_per_epoch:
                raise PollCapacityError(
                    f"Poll capacity reached ({self._max_voters_per_epoch} voters per epoch)."
                )
            ballots[voter_hash] = choice
            tally = self._compute_tally_locked(pack_id, rung_id, epoch)
            return {**tally, "recorded_choice": choice, "recorded_epoch": epoch}

    def reset_poll(self, pack_id: str, rung_id: str) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")
        with self._lock:
            old_epoch = self._epochs.get((pack_id, rung_id), 1)
            self._ballots.pop((pack_id, rung_id, old_epoch), None)
            new_epoch = old_epoch + 1
            self._epochs[(pack_id, rung_id)] = new_epoch
            return self._compute_tally_locked(pack_id, rung_id, new_epoch)

    def get_active_stage_rung(self, pack_id: str) -> str | None:
        _validate_slug(pack_id, "pack_id")
        with self._lock:
            return self._stage_rungs.get(pack_id)

    def set_active_stage_rung(self, pack_id: str, rung_id: str) -> str:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")
        with self._lock:
            self._stage_rungs[pack_id] = rung_id
            return rung_id


class FirestorePollStore:
    """Multi-instance Google Cloud Firestore Native poll store with 1.0s TTL read caching."""

    def __init__(
        self,
        project_id: str,
        database_id: str,
        *,
        client: Any = None,
        cache_ttl_s: float = DEFAULT_POLL_CACHE_TTL_S,
        max_voters_per_epoch: int = MAX_VOTERS_PER_EPOCH,
    ) -> None:
        if not project_id or not project_id.strip():
            raise ValueError("project_id must be non-empty for FirestorePollStore")
        if not database_id or not database_id.strip():
            raise ValueError("database_id must be non-empty for FirestorePollStore")
        if max_voters_per_epoch < 1:
            raise ValueError("max_voters_per_epoch must be >= 1")
        self._project_id = project_id.strip()
        self._database_id = database_id.strip()
        self._client = client
        self._cache_ttl_s = max(0.0, float(cache_ttl_s))
        self._max_voters_per_epoch = max_voters_per_epoch
        self._lock = threading.Lock()
        self._tally_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
        self._tally_inflight_locks: dict[tuple[str, str], threading.Lock] = {}
        self._stage_cache: dict[str, tuple[float, str | None]] = {}

    @property
    def storage_mode(self) -> str:
        return "firestore"

    def _call_firestore(self, op_name: str, fn: Callable[[], _T]) -> _T:
        from google.api_core.exceptions import GoogleAPIError
        from google.auth.exceptions import DefaultCredentialsError

        try:
            return fn()
        except PollError:
            raise
        except (GoogleAPIError, DefaultCredentialsError, ValueError) as exc:
            _logger.warning(
                "Firestore poll %s failed (%s)",
                op_name,
                type(exc).__name__,
            )
            raise PollStoreUnavailableError(
                f"Live poll storage unavailable ({type(exc).__name__})."
            ) from exc

    def _get_tally_lock(self, pack_id: str, rung_id: str) -> threading.Lock:
        with self._lock:
            key = (pack_id, rung_id)
            lock = self._tally_inflight_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._tally_inflight_locks[key] = lock
            return lock

    def _get_client(self) -> Any:
        with self._lock:
            if self._client is None:
                from google.cloud import firestore

                self._client = firestore.Client(
                    project=self._project_id,
                    database=self._database_id,
                )
            return self._client

    def _session_doc_ref(self, client: Any, pack_id: str, rung_id: str) -> Any:
        return client.collection("poll_sessions").document(f"{pack_id}__{rung_id}")

    def _stage_doc_ref(self, client: Any, pack_id: str) -> Any:
        return client.collection("poll_stage").document(pack_id)

    def _query_epoch_ballots(self, session_ref: Any, epoch: int) -> Any:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return session_ref.collection("ballots").where(filter=FieldFilter("epoch", "==", epoch))

    def get_poll_tally(self, pack_id: str, rung_id: str) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")

        now = time.monotonic()
        with self._lock:
            cached = self._tally_cache.get((pack_id, rung_id))
            if cached is not None and (now - cached[0]) < self._cache_ttl_s:
                return _copy_tally(cached[1])

        key_lock = self._get_tally_lock(pack_id, rung_id)
        with key_lock:
            now = time.monotonic()
            with self._lock:
                cached = self._tally_cache.get((pack_id, rung_id))
                if cached is not None and (now - cached[0]) < self._cache_ttl_s:
                    return _copy_tally(cached[1])

            def _fetch() -> dict[str, Any]:
                client = self._get_client()
                session_ref = self._session_doc_ref(client, pack_id, rung_id)
                session_snap = session_ref.get()
                session_data = session_snap.to_dict() if session_snap.exists else {}
                epoch = max(1, int((session_data or {}).get("epoch", 1)))

                counts = _empty_counts()
                for ballot_snap in self._query_epoch_ballots(session_ref, epoch).stream():
                    data = ballot_snap.to_dict() or {}
                    if int(data.get("epoch", epoch)) != epoch:
                        continue
                    choice = str(data.get("choice", ""))
                    if choice in counts:
                        counts[choice] += 1

                return {
                    "pack_id": pack_id,
                    "rung_id": rung_id,
                    "counts": counts,
                    "total_votes": sum(counts.values()),
                    "epoch": epoch,
                    "storage_mode": self.storage_mode,
                }

            tally = self._call_firestore("get_poll_tally", _fetch)
            with self._lock:
                self._tally_cache[(pack_id, rung_id)] = (time.monotonic(), _copy_tally(tally))
            return _copy_tally(tally)

    def cast_vote(
        self,
        pack_id: str,
        rung_id: str,
        choice: str,
        voter_token: str,
    ) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")
        _validate_choice(choice)
        validate_voter_token(voter_token)

        from google.cloud import firestore

        now_iso = _utc_now_iso()

        def _exec_cast() -> int:
            client = self._get_client()
            session_ref = self._session_doc_ref(client, pack_id, rung_id)

            @firestore.transactional
            def _txn_cast(transaction: Any) -> int:
                # 1. ALL READS FIRST (Firestore requires every read before any write).
                session_snap = session_ref.get(transaction=transaction)
                needs_session_init = not session_snap.exists
                if session_snap.exists:
                    session_data = session_snap.to_dict() or {}
                    epoch = max(1, int(session_data.get("epoch", 1)))
                else:
                    epoch = 1

                voter_hash = hash_voter_token(pack_id, rung_id, epoch, voter_token)
                ballot_ref = session_ref.collection("ballots").document(f"e{epoch}_{voter_hash}")
                ballot_snap = ballot_ref.get(transaction=transaction)

                if not ballot_snap.exists:
                    with self._lock:
                        cached = self._tally_cache.get((pack_id, rung_id))
                        cached_valid = (
                            cached is not None
                            and (time.monotonic() - cached[0]) < self._cache_ttl_s
                            and int(cached[1].get("epoch", 0)) == epoch
                        )
                        cached_total = int(cached[1].get("total_votes", 0)) if cached_valid else None
                    if cached_total is not None:
                        current_total = cached_total
                    else:
                        existing_docs = list(
                            self._query_epoch_ballots(session_ref, epoch)
                            .limit(self._max_voters_per_epoch)
                            .stream(transaction=transaction)
                        )
                        current_total = len(existing_docs)
                    if current_total >= self._max_voters_per_epoch:
                        raise PollCapacityError(
                            f"Poll capacity reached ({self._max_voters_per_epoch} voters per epoch)."
                        )

                # 2. ALL WRITES AFTER READS.
                if needs_session_init:
                    transaction.set(
                        session_ref,
                        {
                            "pack_id": pack_id,
                            "rung_id": rung_id,
                            "epoch": epoch,
                            "updated_at": now_iso,
                        },
                    )

                transaction.set(
                    ballot_ref,
                    {
                        "choice": choice,
                        "epoch": epoch,
                        "updated_at": now_iso,
                    },
                )
                return epoch

            return int(_txn_cast(client.transaction()))

        recorded_epoch = self._call_firestore("cast_vote", _exec_cast)
        with self._lock:
            self._tally_cache.pop((pack_id, rung_id), None)
        tally = self.get_poll_tally(pack_id, rung_id)
        recorded_choice = choice if int(tally.get("epoch", recorded_epoch)) == recorded_epoch else None
        return {
            **tally,
            "recorded_choice": recorded_choice,
            "recorded_epoch": recorded_epoch,
        }

    def reset_poll(self, pack_id: str, rung_id: str) -> dict[str, Any]:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")

        from google.cloud import firestore

        now_iso = _utc_now_iso()

        def _exec_reset() -> tuple[Any, Any, int]:
            client = self._get_client()
            session_ref = self._session_doc_ref(client, pack_id, rung_id)

            @firestore.transactional
            def _txn_reset(transaction: Any) -> int:
                session_snap = session_ref.get(transaction=transaction)
                old_epoch = 1
                if session_snap.exists:
                    old_epoch = max(1, int((session_snap.to_dict() or {}).get("epoch", 1)))
                new_epoch = old_epoch + 1
                transaction.set(
                    session_ref,
                    {
                        "pack_id": pack_id,
                        "rung_id": rung_id,
                        "epoch": new_epoch,
                        "updated_at": now_iso,
                    },
                )
                return new_epoch

            new_epoch = int(_txn_reset(client.transaction()))
            return client, session_ref, new_epoch

        client, session_ref, new_epoch = self._call_firestore("reset_poll", _exec_reset)

        # Best-effort deletion of prior-epoch ballot docs in bounded WriteBatch chunks.
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter

            stale_docs = list(
                session_ref.collection("ballots")
                .where(filter=FieldFilter("epoch", "<", new_epoch))
                .limit(_BATCH_DELETE_LIMIT)
                .stream()
            )
            if stale_docs:
                batch = client.batch()
                for doc in stale_docs:
                    batch.delete(doc.reference)
                batch.commit()
        except Exception as exc:
            _logger.warning(
                "Best-effort prior-epoch ballot cleanup failed for %s/%s (%s)",
                pack_id,
                rung_id,
                type(exc).__name__,
            )

        zero_tally = {
            "pack_id": pack_id,
            "rung_id": rung_id,
            "counts": _empty_counts(),
            "total_votes": 0,
            "epoch": new_epoch,
            "storage_mode": self.storage_mode,
        }
        with self._lock:
            self._tally_cache[(pack_id, rung_id)] = (time.monotonic(), _copy_tally(zero_tally))
        return _copy_tally(zero_tally)

    def get_active_stage_rung(self, pack_id: str) -> str | None:
        _validate_slug(pack_id, "pack_id")
        now = time.monotonic()
        with self._lock:
            cached = self._stage_cache.get(pack_id)
            if cached is not None and (now - cached[0]) < self._cache_ttl_s:
                return cached[1]

        def _fetch_stage() -> str | None:
            client = self._get_client()
            snap = self._stage_doc_ref(client, pack_id).get()
            if snap.exists:
                raw = (snap.to_dict() or {}).get("active_rung_id")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
            return None

        active_rung = self._call_firestore("get_active_stage_rung", _fetch_stage)
        with self._lock:
            self._stage_cache[pack_id] = (time.monotonic(), active_rung)
        return active_rung

    def set_active_stage_rung(self, pack_id: str, rung_id: str) -> str:
        _validate_slug(pack_id, "pack_id")
        _validate_slug(rung_id, "rung_id")

        def _write_stage() -> None:
            client = self._get_client()
            self._stage_doc_ref(client, pack_id).set(
                {
                    "active_rung_id": rung_id,
                    "updated_at": _utc_now_iso(),
                }
            )

        self._call_firestore("set_active_stage_rung", _write_stage)
        with self._lock:
            self._stage_cache[pack_id] = (time.monotonic(), rung_id)
        return rung_id
