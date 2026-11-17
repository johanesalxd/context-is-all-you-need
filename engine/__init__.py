"""Engine package for ScenarioPack loading, trust classification, RLS helpers, and bundle export."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "AgentContextError": ("engine.context_retriever", "AgentContextError"),
    "AgentRunResult": ("engine.live_agent", "AgentRunResult"),
    "AgentSqlSecurityError": ("engine.context_retriever", "AgentSqlSecurityError"),
    "BlindToolContext": ("engine.context_retriever", "BlindToolContext"),
    "DEFAULT_REPO_ROOT": ("engine.pack_loader", "DEFAULT_REPO_ROOT"),
    "DataplexCatalogRestClient": ("engine.context_retriever", "DataplexCatalogRestClient"),
    "GovernedToolContext": ("engine.context_retriever", "GovernedToolContext"),
    "ImpersonationError": ("engine.rls_impersonation", "ImpersonationError"),
    "LeakDetectedError": ("engine.bundle_exporter", "LeakDetectedError"),
    "LeakFinding": ("engine.leak_check", "LeakFinding"),
    "NegativeControlError": ("engine.capture_rungs", "NegativeControlError"),
    "NegativeControlResult": ("engine.capture_rungs", "NegativeControlResult"),
    "RoleAssertion": ("engine.rls_impersonation", "RoleAssertion"),
    "TrustAssessment": ("engine.trust_classifier", "TrustAssessment"),
    "TrustTier": ("engine.trust_classifier", "TrustTier"),
    "build_empirical_eval": ("engine.eval_harness", "build_empirical_eval"),
    "build_impersonated_bq_client": ("engine.context_retriever", "build_impersonated_bq_client"),
    "build_impersonated_credentials": ("engine.rls_impersonation", "build_impersonated_credentials"),
    "capture_rungs": ("engine.capture_rungs", "capture_rungs"),
    "classify_outcome": ("engine.trust_classifier", "classify_outcome"),
    "classify_rung_outcome": ("engine.trust_classifier", "classify_rung_outcome"),
    "discover_packs": ("engine.pack_loader", "discover_packs"),
    "discover_rls_target": ("engine.pack_loader", "discover_rls_target"),
    "export_bundle": ("engine.bundle_exporter", "export_bundle"),
    "extract_observed_signals": ("engine.live_agent", "extract_observed_signals"),
    "grade_agent_outcome": ("engine.live_agent", "grade_agent_outcome"),
    "has_assumption_markers": ("engine.trust_classifier", "has_assumption_markers"),
    "is_valid_customer_sa": ("engine.rls_impersonation", "is_valid_customer_sa"),
    "load_context_layer": ("engine.pack_loader", "load_context_layer"),
    "load_dotenv_if_present": ("engine.pack_loader", "load_dotenv_if_present"),
    "load_pack": ("engine.pack_loader", "load_pack"),
    "load_raw_pack": ("engine.pack_loader", "load_raw_pack"),
    "load_schema": ("engine.pack_loader", "load_schema"),
    "load_seed_module": ("engine.pack_loader", "load_seed_module"),
    "mint_hmac_role_assertion": ("engine.rls_impersonation", "mint_hmac_role_assertion"),
    "normalize_sql_for_match": ("engine.trust_classifier", "normalize_sql_for_match"),
    "parse_agent_sa_map": ("engine.rls_impersonation", "parse_agent_sa_map"),
    "parse_bool_flag": ("engine.pack_loader", "parse_bool_flag"),
    "parse_role_sa_map": ("engine.rls_impersonation", "parse_role_sa_map"),
    "reconcile_outcome_metric": ("engine.trust_classifier", "reconcile_outcome_metric"),
    "reconcile_prose_numbers": ("engine.trust_classifier", "reconcile_prose_numbers"),
    "redact_bundle_data": ("engine.rls_impersonation", "redact_bundle_data"),
    "redact_sensitive_identifiers": ("engine.rls_impersonation", "redact_sensitive_identifiers"),
    "render_bundle_placeholders": ("engine.pack_loader", "render_bundle_placeholders"),
    "resolve_agent_sa_map": ("engine.rls_impersonation", "resolve_agent_sa_map"),
    "resolve_env_settings": ("engine.pack_loader", "resolve_env_settings"),
    "resolve_execution_sa": ("engine.context_retriever", "resolve_execution_sa"),
    "resolve_phase2_settings": ("engine.pack_loader", "resolve_phase2_settings"),
    "run_eval_harness": ("engine.eval_harness", "run_eval_harness"),
    "run_live_agent_arm": ("engine.live_agent", "run_live_agent_arm"),
    "run_offline_mock_arm": ("engine.live_agent", "run_offline_mock_arm"),
    "scan_repo_for_leaks": ("engine.leak_check", "scan_repo_for_leaks"),
    "scan_text_for_leaks": ("engine.leak_check", "scan_text_for_leaks"),
    "select_median_token_representative": ("engine.eval_harness", "select_median_token_representative"),
    "strip_sql_literals_and_comments": ("engine.trust_classifier", "strip_sql_literals_and_comments"),
    "validate_agent_sql_gate": ("engine.context_retriever", "validate_agent_sql_gate"),
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
