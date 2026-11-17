"""Engine package for ScenarioPack loading, trust classification, RLS helpers, and bundle export."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "DEFAULT_REPO_ROOT": ("engine.pack_loader", "DEFAULT_REPO_ROOT"),
    "ImpersonationError": ("engine.rls_impersonation", "ImpersonationError"),
    "LeakDetectedError": ("engine.bundle_exporter", "LeakDetectedError"),
    "LeakFinding": ("engine.leak_check", "LeakFinding"),
    "NegativeControlError": ("engine.capture_rungs", "NegativeControlError"),
    "NegativeControlResult": ("engine.capture_rungs", "NegativeControlResult"),
    "RoleAssertion": ("engine.rls_impersonation", "RoleAssertion"),
    "TrustAssessment": ("engine.trust_classifier", "TrustAssessment"),
    "TrustTier": ("engine.trust_classifier", "TrustTier"),
    "build_impersonated_credentials": ("engine.rls_impersonation", "build_impersonated_credentials"),
    "capture_rungs": ("engine.capture_rungs", "capture_rungs"),
    "classify_outcome": ("engine.trust_classifier", "classify_outcome"),
    "classify_rung_outcome": ("engine.trust_classifier", "classify_rung_outcome"),
    "discover_packs": ("engine.pack_loader", "discover_packs"),
    "export_bundle": ("engine.bundle_exporter", "export_bundle"),
    "has_assumption_markers": ("engine.trust_classifier", "has_assumption_markers"),
    "is_valid_customer_sa": ("engine.rls_impersonation", "is_valid_customer_sa"),
    "load_dotenv_if_present": ("engine.pack_loader", "load_dotenv_if_present"),
    "load_pack": ("engine.pack_loader", "load_pack"),
    "load_raw_pack": ("engine.pack_loader", "load_raw_pack"),
    "load_schema": ("engine.pack_loader", "load_schema"),
    "load_seed_module": ("engine.pack_loader", "load_seed_module"),
    "mint_hmac_role_assertion": ("engine.rls_impersonation", "mint_hmac_role_assertion"),
    "normalize_sql_for_match": ("engine.trust_classifier", "normalize_sql_for_match"),
    "parse_role_sa_map": ("engine.rls_impersonation", "parse_role_sa_map"),
    "reconcile_outcome_metric": ("engine.trust_classifier", "reconcile_outcome_metric"),
    "reconcile_prose_numbers": ("engine.trust_classifier", "reconcile_prose_numbers"),
    "redact_bundle_data": ("engine.rls_impersonation", "redact_bundle_data"),
    "redact_sensitive_identifiers": ("engine.rls_impersonation", "redact_sensitive_identifiers"),
    "render_bundle_placeholders": ("engine.pack_loader", "render_bundle_placeholders"),
    "resolve_env_settings": ("engine.pack_loader", "resolve_env_settings"),
    "scan_repo_for_leaks": ("engine.leak_check", "scan_repo_for_leaks"),
    "scan_text_for_leaks": ("engine.leak_check", "scan_text_for_leaks"),
    "strip_sql_literals_and_comments": ("engine.trust_classifier", "strip_sql_literals_and_comments"),
    "validate_bundle": ("engine.pack_loader", "validate_bundle"),
    "verify_negative_governance_control": ("engine.capture_rungs", "verify_negative_governance_control"),
    "verify_role_assertion": ("engine.rls_impersonation", "verify_role_assertion"),
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        module_name, attr_name = _EXPORTS[name]
        module = importlib.import_module(module_name)
        return getattr(module, attr_name)
    raise AttributeError(f"module 'engine' has no attribute {name!r}")
