"""Signed role assertion verification, customer SA validation, and identifier redaction.

The HMAC role-assertion primitives (`mint_hmac_role_assertion` / `verify_role_assertion`)
are provided as reusable library primitives for external gateways; the local Workbench
runner relies on `SQL_ROLE_SA_MAP_JSON` / BigQuery policy grantees without HTTP HMAC headers.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

__all__ = [
    "ImpersonationError",
    "RoleAssertion",
    "build_impersonated_credentials",
    "is_valid_customer_sa",
    "mint_hmac_role_assertion",
    "parse_agent_sa_map",
    "parse_role_sa_map",
    "redact_bundle_data",
    "redact_sensitive_identifiers",
    "resolve_agent_sa_map",
    "verify_role_assertion",
]

_ROLE_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
_CUSTOMER_SA_REGEX = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com$"
)
_SA_EMAIL_REDACTION_REGEX = re.compile(
    r"\b[A-Za-z0-9._+-]+@[A-Za-z0-9.-]*gserviceaccount\.com\b",
    re.IGNORECASE,
)
_USER_EMAIL_REDACTION_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

_REDACTED_SA = "redacted-sa@example-project-id.iam.gserviceaccount.com"
_REDACTED_USER = "redacted-user@example.com"
_PLACEHOLDER_PROJECT = "example-project-id"


class ImpersonationError(ValueError):
    """Raised when role assertion verification, SA validation, or impersonation fails."""


@dataclass(frozen=True)
class RoleAssertion:
    """Verified identity assertion binding a subject to an allowlisted BigQuery role."""

    role: str
    subject: str
    expires_at: int
    issuer: str
    job_labels: dict[str, str]


def _is_google_managed_sa(email: str) -> bool:
    """Returns True when an email matches a Google-managed service agent pattern."""
    lowered = email.strip().lower()
    return (
        "@gcp-sa-" in lowered
        or lowered.endswith(".cloudservices.gserviceaccount.com")
        or lowered.endswith("@cloudservices.gserviceaccount.com")
        or lowered.endswith(".developer.gserviceaccount.com")
        or lowered.endswith("@developer.gserviceaccount.com")
        or lowered.endswith("@appspot.gserviceaccount.com")
    )


def is_valid_customer_sa(email: str) -> bool:
    """Validates a customer-managed IAM service account email."""
    if not isinstance(email, str):
        return False
    cleaned = email.strip()
    return bool(_CUSTOMER_SA_REGEX.match(cleaned)) and not _is_google_managed_sa(cleaned)


def _parse_sa_map(
    raw_json: str | None,
    *,
    env_name: str,
) -> dict[str, str]:
    """Parses and validates a JSON mapping of slugs to customer-managed service accounts."""
    if raw_json is None or not raw_json.strip():
        raise ImpersonationError(f"{env_name} cannot be empty or None")

    def _pairs_hook(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, val in pairs:
            if key in result:
                raise ImpersonationError(f"Duplicate role key in {env_name}: {key!r}")
            result[key] = val
        return result

    try:
        data = json.loads(raw_json, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as err:
        raise ImpersonationError(f"Malformed JSON in {env_name}: {err}") from err

    if not isinstance(data, dict) or not data:
        raise ImpersonationError(f"{env_name} must be a non-empty JSON object")

    validated: dict[str, str] = {}
    for role, sa_email in data.items():
        if not isinstance(role, str) or not _ROLE_REGEX.match(role):
            raise ImpersonationError(
                f"Invalid role slug {role!r}; must match ^[a-z0-9][a-z0-9_-]{{0,62}}$"
            )
        if not isinstance(sa_email, str):
            raise ImpersonationError(
                f"Service account for role {role!r} must be a string, got {type(sa_email).__name__}"
            )
        sa_clean = sa_email.strip()
        if not is_valid_customer_sa(sa_clean):
            raise ImpersonationError(
                f"Role {role!r} maps to an invalid service account email: {sa_clean!r}. "
                "Must be a customer-managed service account (*.iam.gserviceaccount.com)."
            )
        validated[role] = sa_clean

    return validated


def parse_role_sa_map(raw_json: str | None) -> dict[str, str]:
    """Parses and validates a JSON mapping of role slugs to customer-managed service accounts."""
    return _parse_sa_map(raw_json, env_name="SQL_ROLE_SA_MAP_JSON")


def parse_agent_sa_map(raw_json: str | None) -> dict[str, str]:
    """Parses AGENT_SA_MAP_JSON ensuring strict blind/governed SA isolation."""
    validated = _parse_sa_map(raw_json, env_name="AGENT_SA_MAP_JSON")
    required = {"blind", "governed"}
    missing = required - set(validated.keys())
    if missing:
        raise ImpersonationError(
            f"AGENT_SA_MAP_JSON missing required arm key(s): {sorted(missing)}"
        )
    if validated["blind"] == validated["governed"]:
        raise ImpersonationError("AGENT_SA_MAP_JSON blind and governed SAs must be distinct")
    for arm, sa_email in validated.items():
        if "web-runner" in sa_email.lower():
            raise ImpersonationError(
                f"AGENT_SA_MAP_JSON arm {arm!r} cannot use web-runner SA: {sa_email!r}"
            )
    return validated


def resolve_agent_sa_map(
    *,
    project_id: str,
    pack_id: str = "",
    env_json: str | None = None,
    context_layer: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Resolves distinct blind and governed customer SAs from env, context_layer, or pack prefix."""
    raw_env = env_json if env_json is not None else os.getenv("AGENT_SA_MAP_JSON")
    if raw_env is not None and raw_env.strip():
        return parse_agent_sa_map(raw_env)

    prefix_raw = ""
    if context_layer and isinstance(context_layer.get("agent_sa_prefix"), str):
        prefix_raw = context_layer["agent_sa_prefix"].strip().lower()
    if not prefix_raw and pack_id:
        prefix_raw = pack_id.split("_")[0].strip().lower()
    prefix_clean = re.sub(r"[^a-z0-9-]", "-", prefix_raw or "agent").strip("-") or "agent"
    prefix_clean = prefix_clean[:15].rstrip("-") or "agent"

    blind_sa = f"{prefix_clean}-blind-agent@{project_id}.iam.gserviceaccount.com"
    governed_sa = f"{prefix_clean}-governed-agent@{project_id}.iam.gserviceaccount.com"

    if context_layer and isinstance(context_layer.get("agent_sas"), Mapping):
        sas_cfg = context_layer["agent_sas"]
        if isinstance(sas_cfg.get("blind"), str) and sas_cfg["blind"].strip():
            blind_sa = sas_cfg["blind"].strip()
        if isinstance(sas_cfg.get("governed"), str) and sas_cfg["governed"].strip():
            governed_sa = sas_cfg["governed"].strip()

    return parse_agent_sa_map(json.dumps({"blind": blind_sa, "governed": governed_sa}))


def mint_hmac_role_assertion(
    role: str,
    subject: str,
    *,
    hmac_secret: str,
    audience: str = "context-pack-rls",
    ttl_seconds: int = 300,
    now: int | None = None,
) -> str:
    """Mints a compact HMAC-SHA256 signed role assertion ('v1.<payload>.<sig>')."""
    if len(hmac_secret) < 32:
        raise ImpersonationError("HMAC secret must be at least 32 characters")
    if not (1 <= ttl_seconds <= 3600):
        raise ImpersonationError("ttl_seconds must be between 1 and 3600")
    if not _ROLE_REGEX.match(role):
        raise ImpersonationError(f"Invalid role slug: {role!r}")
    sub = subject.strip()
    if not sub:
        raise ImpersonationError("subject must not be empty")

    ts = int(time.time() if now is None else now)
    payload = {
        "aud": audience,
        "role": role,
        "exp": ts + ttl_seconds,
        "iat": ts,
        "iss": "hmac-local",
        "sub": sub,
    }
    raw_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")
    sig = hmac.new(hmac_secret.encode("utf-8"), raw_bytes, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"v1.{payload_b64}.{sig_b64}"


def verify_role_assertion(
    assertion: str | None,
    *,
    hmac_secret: str | None = None,
    expected_audience: str = "context-pack-rls",
    now: int | None = None,
    max_ttl_seconds: int = 900,
    expected_subject: str | None = None,
) -> RoleAssertion:
    """Verifies a local HMAC-SHA256 role assertion using constant-time comparison."""
    if assertion is None or not assertion.strip():
        raise ImpersonationError("Role assertion cannot be empty or None")
    if hmac_secret is None or len(hmac_secret.strip()) < 32:
        raise ImpersonationError("HMAC secret must be configured and at least 32 characters")

    secret = hmac_secret.strip()
    token = assertion.strip()
    current_ts = int(time.time() if now is None else now)

    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise ImpersonationError("Invalid HMAC assertion format; expected 'v1.<payload>.<sig>'")

    _, payload_b64, sig_b64 = parts
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
        actual_sig = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
    except Exception as err:
        raise ImpersonationError(f"Malformed base64url encoding in assertion: {err}") from err

    expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ImpersonationError("Invalid role assertion HMAC signature")

    try:
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception as err:
        raise ImpersonationError(f"Malformed JSON payload in assertion: {err}") from err

    if not isinstance(claims, dict):
        raise ImpersonationError("Assertion payload must be a JSON object")

    if claims.get("aud") != expected_audience:
        raise ImpersonationError(
            f"Role assertion audience mismatch: expected {expected_audience!r}, got {claims.get('aud')!r}"
        )

    iss = str(claims.get("iss", "")).strip()
    if iss != "hmac-local":
        raise ImpersonationError(f"HMAC assertion must have iss='hmac-local', got {iss!r}")

    iat_raw = claims.get("iat")
    exp_raw = claims.get("exp")
    if iat_raw is None or exp_raw is None:
        raise ImpersonationError("Role assertion missing 'iat' or 'exp' claim")
    try:
        iat = int(iat_raw)
        exp = int(exp_raw)
    except (ValueError, TypeError) as err:
        raise ImpersonationError("Role assertion has invalid integer timestamps") from err

    if iat <= 0 or iat > current_ts + 60:
        raise ImpersonationError(f"Role assertion 'iat' out of valid window (iat={iat})")
    if exp <= current_ts:
        raise ImpersonationError(f"Role assertion has expired (exp={exp}, current={current_ts})")
    ttl = exp - iat
    if ttl <= 0 or ttl > max_ttl_seconds:
        raise ImpersonationError(
            f"Role assertion TTL ({ttl}s) must be positive and <= {max_ttl_seconds}s"
        )

    sub = str(claims.get("sub", "")).strip()
    if not sub:
        raise ImpersonationError("Role assertion missing non-empty 'sub' claim")
    if expected_subject is not None and expected_subject.strip():
        if sub != expected_subject.strip():
            raise ImpersonationError(
                f"Role assertion subject mismatch: expected {expected_subject.strip()!r}, got {sub!r}"
            )

    role = str(claims.get("role", claims.get("bqca_role", ""))).strip()
    if not _ROLE_REGEX.match(role):
        raise ImpersonationError(f"Role assertion contains invalid role: {role!r}")

    user_hash = hashlib.sha256(f"context-audit:{sub}".encode("utf-8")).hexdigest()[:16]
    return RoleAssertion(
        role=role,
        subject=sub,
        expires_at=exp,
        issuer=iss,
        job_labels={
            "context-role": role,
            "context-user-hash": user_hash,
        },
    )


def build_impersonated_credentials(
    *,
    role: str,
    role_sa_map: Mapping[str, str] | None = None,
    target_scopes: Sequence[str] = ("https://www.googleapis.com/auth/cloud-platform",),
    lifetime_seconds: int = 300,
    source_credentials: Any = None,
) -> tuple[Any, str]:
    """Builds scoped impersonated credentials for an allowlisted role slug."""
    if not (60 <= lifetime_seconds <= 3600):
        raise ImpersonationError("lifetime_seconds must be between 60 and 3600")
    if not target_scopes:
        raise ImpersonationError("target_scopes cannot be empty")

    resolved_map = (
        dict(role_sa_map)
        if role_sa_map is not None
        else parse_role_sa_map(os.getenv("SQL_ROLE_SA_MAP_JSON"))
    )
    if role not in resolved_map:
        raise ImpersonationError(f"Role {role!r} is not mapped in SQL_ROLE_SA_MAP_JSON")

    target_sa = resolved_map[role]
    if not is_valid_customer_sa(target_sa):
        raise ImpersonationError(f"Mapped service account for {role!r} is invalid")

    try:
        import google.auth
        from google.auth import impersonated_credentials
    except ImportError as err:  # pragma: no cover - dependency guard
        raise ImpersonationError("google-auth is required for SA impersonation") from err

    src_creds = source_credentials
    if src_creds is None:
        src_creds, _ = google.auth.default(scopes=list(target_scopes))

    creds = impersonated_credentials.Credentials(
        source_credentials=src_creds,
        target_principal=target_sa,
        target_scopes=list(target_scopes),
        lifetime=lifetime_seconds,
    )
    return creds, target_sa


def _scrub_sa_match(match: re.Match[str]) -> str:
    email = match.group(0)
    if email.lower().endswith(f"@{_PLACEHOLDER_PROJECT}.iam.gserviceaccount.com"):
        return email
    return _REDACTED_SA


def _scrub_user_match(match: re.Match[str]) -> str:
    email = match.group(0)
    lowered = email.lower()
    if lowered == _REDACTED_USER or lowered.endswith(
        f"@{_PLACEHOLDER_PROJECT}.iam.gserviceaccount.com"
    ):
        return email
    return _REDACTED_USER


def redact_sensitive_identifiers(
    text: str | None,
    *,
    extra_tokens: Iterable[str] | None = None,
    live_project_id: str | None = None,
) -> str:
    """Scrubs SA emails, user emails, and live GCP project IDs from text."""
    if not text:
        return ""

    result = _SA_EMAIL_REDACTION_REGEX.sub(_scrub_sa_match, text)
    result = _USER_EMAIL_REDACTION_REGEX.sub(_scrub_user_match, result)

    tokens_to_scrub: set[str] = set()
    if live_project_id:
        pid = live_project_id.strip()
        if pid and pid != _PLACEHOLDER_PROJECT:
            tokens_to_scrub.add(pid)
    else:
        env_pid = os.environ.get("PROJECT_ID", "").strip()
        if env_pid and env_pid != _PLACEHOLDER_PROJECT and len(env_pid) >= 6:
            tokens_to_scrub.add(env_pid)

    if extra_tokens:
        for tok in extra_tokens:
            cleaned = tok.strip()
            if cleaned and cleaned != _PLACEHOLDER_PROJECT:
                tokens_to_scrub.add(cleaned)

    for token in sorted(tokens_to_scrub, key=len, reverse=True):
        result = result.replace(token, _PLACEHOLDER_PROJECT)

    return result


def redact_bundle_data(
    value: Any,
    *,
    extra_tokens: Iterable[str] | None = None,
    live_project_id: str | None = None,
) -> Any:
    """Recursively redacts sensitive identifiers across dicts, lists, and strings."""
    if isinstance(value, str):
        return redact_sensitive_identifiers(
            value,
            extra_tokens=extra_tokens,
            live_project_id=live_project_id,
        )
    if isinstance(value, list):
        return [
            redact_bundle_data(
                item,
                extra_tokens=extra_tokens,
                live_project_id=live_project_id,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: redact_bundle_data(
                item,
                extra_tokens=extra_tokens,
                live_project_id=live_project_id,
            )
            for key, item in value.items()
        }
    return value
