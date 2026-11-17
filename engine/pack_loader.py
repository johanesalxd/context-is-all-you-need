"""Dynamic ScenarioPack discovery, placeholder substitution, and schema validation."""

from __future__ import annotations

from collections.abc import Mapping
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Any

import jsonschema
import yaml

__all__ = [
    "DEFAULT_REPO_ROOT",
    "discover_packs",
    "discover_rls_target",
    "extract_create_table_statement",
    "load_context_layer",
    "load_dotenv_if_present",
    "load_pack",
    "load_raw_pack",
    "load_schema",
    "load_seed_module",
    "render_bundle_placeholders",
    "resolve_bq_location",
    "resolve_env_settings",
    "resolve_phase2_settings",
    "validate_bundle",
]

DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
_PACK_ID_REGEX = re.compile(r"^[a-z0-9_]+$")
_PLACEHOLDER_PROJECT = "example-project-id"


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parses simple KEY=VALUE lines from an env file without executing shell code."""
    if not env_path.is_file():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
            val = val[1:-1]
        parsed[key] = val
    return parsed


def load_dotenv_if_present(
    dotenv_path: Path | None = None,
    *,
    override: bool = False,
) -> dict[str, str]:
    """Loads untracked .env key/value pairs without overriding explicit env vars."""
    path = dotenv_path or (DEFAULT_REPO_ROOT / ".env")
    values = parse_env_file(path)
    for key, val in values.items():
        if override or key not in os.environ:
            os.environ[key] = val
    return values


def resolve_env_settings(
    repo_root: Path | None = None,
    *,
    env_file: Path | None = None,
) -> dict[str, str]:
    """Resolves runtime GCP/pack settings from environment, .env, and .env.example."""
    root = repo_root or DEFAULT_REPO_ROOT
    dotenv = env_file or (root / ".env")
    load_dotenv_if_present(dotenv, override=False)

    example_defaults = parse_env_file(root / ".env.example")
    project_id = os.environ.get("PROJECT_ID") or _PLACEHOLDER_PROJECT
    dataset_id = os.environ.get("DATASET_ID") or example_defaults.get("DATASET_ID") or "example_dataset"
    bq_location = os.environ.get("BQ_LOCATION") or example_defaults.get("BQ_LOCATION") or "asia-southeast1"
    pack_id = os.environ.get("PACK_ID") or example_defaults.get("PACK_ID") or ""

    return {
        "PROJECT_ID": project_id,
        "DATASET_ID": dataset_id,
        "BQ_LOCATION": bq_location,
        "PACK_ID": pack_id,
    }


def _env_or_default(key: str, example_defaults: Mapping[str, str], fallback: str) -> str:
    val = os.environ.get(key)
    if val is not None and val.strip() != "":
        return val.strip()
    ex = example_defaults.get(key)
    if ex is not None and ex.strip() != "":
        return ex.strip()
    return fallback


def parse_bool_flag(raw: str | None, *, default: bool) -> bool:
    """Parses environment boolean strings safely."""
    if raw is None or not raw.strip():
        return default
    cleaned = raw.strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_phase2_settings(
    repo_root: Path | None = None,
    *,
    env_file: Path | None = None,
    pack_id: str | None = None,
) -> dict[str, str]:
    """Resolves Phase 1 + Phase 2 live Knowledge Catalog & Agent settings."""
    root = repo_root or DEFAULT_REPO_ROOT
    base = resolve_env_settings(root, env_file=env_file)
    example_defaults = parse_env_file(root / ".env.example")
    resolved_pack = pack_id or base["PACK_ID"]
    prefix = resolved_pack.split("_")[0] if resolved_pack else "example"
    default_blind_ds = f"{prefix}_blind" if prefix else "example_blind"

    return {
        **base,
        "BLIND_DATASET_ID": _env_or_default("BLIND_DATASET_ID", example_defaults, default_blind_ds),
        "AGENT_MODEL_ID": _env_or_default("AGENT_MODEL_ID", example_defaults, "gemini-3.8-flash"),
        "AGENT_MODEL_LOCATION": _env_or_default("AGENT_MODEL_LOCATION", example_defaults, "global"),
        "BQ_CONNECTION_ID": _env_or_default("BQ_CONNECTION_ID", example_defaults, f"{prefix}_vertex_conn"),
        "ENABLE_LIVE_AGENT": _env_or_default("ENABLE_LIVE_AGENT", example_defaults, "true"),
        "REQUIRE_TOKEN_FOR_LIVE_AGENT": _env_or_default("REQUIRE_TOKEN_FOR_LIVE_AGENT", example_defaults, "true"),
        "REQUIRE_TOKEN_FOR_RUN_RUNG": _env_or_default("REQUIRE_TOKEN_FOR_RUN_RUNG", example_defaults, "false"),
        "DAILY_AGENT_CALL_LIMIT": _env_or_default("DAILY_AGENT_CALL_LIMIT", example_defaults, "200"),
        "EVAL_RUNS": _env_or_default("EVAL_RUNS", example_defaults, "5"),
    }


def resolve_bq_location(
    raw_bundle: Mapping[str, Any],
    *,
    env_settings: Mapping[str, str],
) -> str:
    """Resolves BigQuery execution location with precedence: env/.env > pack region > default."""
    explicit_env_loc = os.environ.get("BQ_LOCATION", "").strip()
    if explicit_env_loc:
        return explicit_env_loc
    pack_region = str(raw_bundle.get("region") or "").strip()
    if pack_region:
        return pack_region
    return str(env_settings.get("BQ_LOCATION") or "asia-southeast1").strip()


def _strip_sql_comments(sql_text: str) -> list[str]:
    """Splits GoogleSQL into comment-free statements using literal-aware tokenization."""
    from engine.trust_classifier import TokenType, tokenize_googlesql

    statements: list[str] = []
    parts: list[str] = []
    for tok in tokenize_googlesql(sql_text):
        if tok.type == TokenType.COMMENT:
            parts.append(" ")
            continue
        parts.append(tok.text)
        if tok.type == TokenType.PUNCT and tok.text == ";":
            stmt = "".join(parts).strip()
            if stmt:
                statements.append(stmt)
            parts = []
    tail = "".join(parts).strip()
    if tail:
        statements.append(tail)
    return statements


def extract_create_table_statement(sql_text: str, table_name: str) -> str | None:
    """Extracts the CREATE TABLE statement targeting table_name after stripping SQL comments."""
    target = table_name.strip().lower()
    if not target:
        return None
    header_re = re.compile(
        r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(;]+)",
        flags=re.IGNORECASE,
    )
    for stmt in _strip_sql_comments(sql_text):
        match = header_re.match(stmt)
        if not match:
            continue
        ident = match.group(1).strip().strip("`\"")
        leaf = ident.split(".")[-1].strip("`\"").lower()
        if leaf == target:
            return stmt
    return None


def discover_packs(packs_dir: Path | None = None) -> list[str]:
    """Returns sorted pack IDs containing a pack.yaml file under packs_dir."""
    base = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    if not base.is_dir():
        return []
    found: list[str] = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and _PACK_ID_REGEX.match(entry.name) and (entry / "pack.yaml").is_file():
            found.append(entry.name)
    return found


def substitute_placeholders(
    value: Any,
    *,
    project_id: str,
    dataset_id: str,
    bq_location: str,
    extra: Mapping[str, str] | None = None,
) -> Any:
    """Recursively replaces ${PROJECT_ID}, ${DATASET_ID}, ${BQ_LOCATION} placeholders."""
    if isinstance(value, str):
        rendered = (
            value.replace("${PROJECT_ID}", project_id)
            .replace("${DATASET_ID}", dataset_id)
            .replace("${BQ_LOCATION}", bq_location)
        )
        if extra:
            for key, replacement in extra.items():
                rendered = rendered.replace(f"${{{key}}}", replacement)
        return rendered
    if isinstance(value, list):
        return [
            substitute_placeholders(
                item,
                project_id=project_id,
                dataset_id=dataset_id,
                bq_location=bq_location,
                extra=extra,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: substitute_placeholders(
                item,
                project_id=project_id,
                dataset_id=dataset_id,
                bq_location=bq_location,
                extra=extra,
            )
            for key, item in value.items()
        }
    return value


def render_bundle_placeholders(
    bundle: Mapping[str, Any],
    *,
    project_id: str,
    dataset_id: str,
    bq_location: str,
    extra: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Returns a deep copy of a pack bundle with placeholders substituted."""
    rendered = substitute_placeholders(
        dict(bundle),
        project_id=project_id,
        dataset_id=dataset_id,
        bq_location=bq_location,
        extra=extra,
    )
    return dict(rendered)


def load_schema(schema_path: Path | None = None) -> dict[str, Any]:
    """Loads the ContextScenarioPackBundleV2 JSON Schema."""
    path = schema_path or (DEFAULT_REPO_ROOT / "schemas" / "rung_v2.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_bundle(
    bundle: Mapping[str, Any],
    *,
    schema_path: Path | None = None,
) -> None:
    """Validates a bundle dictionary against schemas/rung_v2.schema.json."""
    schema = load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(dict(bundle))


def load_raw_pack(
    pack_id: str,
    *,
    packs_dir: Path | None = None,
) -> dict[str, Any]:
    """Loads pack.yaml and rungs/*.yaml sorted by rung_num without placeholder substitution."""
    if not _PACK_ID_REGEX.match(pack_id):
        raise ValueError(f"Invalid pack_id format: {pack_id!r}")

    base = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    pack_root = (base / pack_id).resolve()
    if base.resolve() not in pack_root.parents:
        raise ValueError(f"Pack path escapes packs directory: {pack_id!r}")
    if not pack_root.is_dir():
        raise FileNotFoundError(f"Pack directory not found: {pack_root}")

    pack_yaml_path = pack_root / "pack.yaml"
    if not pack_yaml_path.is_file():
        raise FileNotFoundError(f"pack.yaml not found in {pack_root}")

    pack_data = yaml.safe_load(pack_yaml_path.read_text(encoding="utf-8"))
    if not isinstance(pack_data, dict):
        raise ValueError(f"pack.yaml must decode to a mapping: {pack_yaml_path}")

    rungs_dir = pack_root / "rungs"
    rungs: list[dict[str, Any]] = []
    if rungs_dir.is_dir():
        rung_files = sorted(
            p for p in rungs_dir.iterdir() if p.is_file() and p.suffix in (".yaml", ".yml")
        )
        loaded_with_names: list[tuple[int, str, dict[str, Any]]] = []
        for rung_file in rung_files:
            rung_obj = yaml.safe_load(rung_file.read_text(encoding="utf-8"))
            if not isinstance(rung_obj, dict):
                raise ValueError(f"Rung YAML must decode to a mapping: {rung_file}")
            rung_num = int(rung_obj.get("rung_num", 0))
            loaded_with_names.append((rung_num, rung_file.name, rung_obj))
        loaded_with_names.sort(key=lambda item: (item[0], item[1]))
        rungs = [item[2] for item in loaded_with_names]

    bundle = dict(pack_data)
    if rungs:
        bundle["rungs"] = rungs
    elif "rungs" not in bundle:
        bundle["rungs"] = []

    return bundle


def load_pack(
    pack_id: str,
    *,
    packs_dir: Path | None = None,
    schema_path: Path | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    bq_location: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Loads, renders placeholders, and validates a ScenarioPack bundle."""
    raw_bundle = load_raw_pack(pack_id, packs_dir=packs_dir)
    env_defaults = resolve_env_settings()
    resolved_project = project_id or _PLACEHOLDER_PROJECT
    resolved_dataset = dataset_id or env_defaults["DATASET_ID"]
    resolved_location = bq_location or resolve_bq_location(raw_bundle, env_settings=env_defaults)

    bundle = render_bundle_placeholders(
        raw_bundle,
        project_id=resolved_project,
        dataset_id=resolved_dataset,
        bq_location=resolved_location,
    )
    if validate:
        validate_bundle(bundle, schema_path=schema_path)
    return bundle


def load_seed_module(
    pack_id: str,
    *,
    packs_dir: Path | None = None,
) -> ModuleType | None:
    """Dynamically imports packs/<pack_id>/seed*.py via importlib if present."""
    if not _PACK_ID_REGEX.match(pack_id):
        raise ValueError(f"Invalid pack_id format: {pack_id!r}")
    base = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    pack_root = base / pack_id
    if not pack_root.is_dir():
        raise FileNotFoundError(f"Pack directory not found: {pack_root}")

    seed_files = sorted(pack_root.glob("seed*.py"))
    if not seed_files:
        return None

    seed_path = seed_files[0]
    mod_name = f"scenario_pack_seed_{pack_id}_{seed_path.stem}_{abs(hash(str(seed_path.resolve())))}"
    spec = importlib.util.spec_from_file_location(mod_name, seed_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create module spec for {seed_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def load_context_layer(
    pack_id: str,
    *,
    packs_dir: Path | None = None,
    project_id: str | None = None,
    dataset_id: str | None = None,
    bq_location: str | None = None,
) -> dict[str, Any]:
    """Loads packs/<pack_id>/context_layer.yaml, optionally substituting placeholders."""
    if not _PACK_ID_REGEX.match(pack_id):
        raise ValueError(f"Invalid pack_id format: {pack_id!r}")
    base = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    pack_root = (base / pack_id).resolve()
    if base.resolve() not in pack_root.parents:
        raise ValueError(f"Pack path escapes packs directory: {pack_id!r}")
    ctx_path = pack_root / "context_layer.yaml"
    if not ctx_path.is_file():
        raise FileNotFoundError(f"context_layer.yaml not found in {pack_root}")
    data = yaml.safe_load(ctx_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"context_layer.yaml must decode to a mapping: {ctx_path}")
    if project_id or dataset_id or bq_location:
        data = substitute_placeholders(
            data,
            project_id=project_id or _PLACEHOLDER_PROJECT,
            dataset_id=dataset_id or "example_dataset",
            bq_location=bq_location or "asia-southeast1",
        )
    return dict(data)


def discover_rls_target(
    pack_id: str,
    *,
    packs_dir: Path | None = None,
) -> tuple[str | None, str | None]:
    """Discovers (table_name, cfo_policy_name) dynamically from context_layer.yaml or sql/03_rls.sql."""
    base = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    pack_root = (base / pack_id).resolve()
    if base.resolve() not in pack_root.parents or not pack_root.is_dir():
        return None, None

    rls_sql_path = pack_root / "sql" / "03_rls.sql"
    if rls_sql_path.is_file():
        sql_text = rls_sql_path.read_text(encoding="utf-8")
        policy_re = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?ROW\s+ACCESS\s+POLICY\s+([^\s]+)\s+ON\s+([^\s(]+)",
            re.IGNORECASE,
        )
        found_policies: list[tuple[str, str]] = []
        for stmt in _strip_sql_comments(sql_text):
            m = policy_re.search(stmt)
            if m:
                pol_name = m.group(1).strip().strip("`\"")
                tbl_ident = m.group(2).strip().strip("`\"")
                tbl_leaf = tbl_ident.split(".")[-1].strip("`\"")
                found_policies.append((tbl_leaf, pol_name))
        if found_policies:
            for tbl_leaf, pol_name in found_policies:
                low = pol_name.lower()
                if "cfo" in low or "all" in low or "regional" in low or "global" in low:
                    return tbl_leaf, pol_name
            return found_policies[0]

    ctx_path = pack_root / "context_layer.yaml"
    if ctx_path.is_file():
        ctx = yaml.safe_load(ctx_path.read_text(encoding="utf-8")) or {}
        if isinstance(ctx, Mapping):
            if isinstance(ctx.get("rls_table"), str) and ctx["rls_table"].strip():
                return ctx["rls_table"].strip(), str(ctx.get("rls_cfo_policy") or "") or None
            for dq in ctx.get("data_quality_scans") or []:
                if isinstance(dq, Mapping) and isinstance(dq.get("target_table"), str):
                    return dq["target_table"].strip(), None

    return None, None
