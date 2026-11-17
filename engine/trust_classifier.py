"""Stateless 3-Tier Trust classifier, literal-safe SQL/GQL normalizer, and numeric reconciler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto
import math
import re
from typing import Any

__all__ = [
    "Token",
    "TokenType",
    "TrustAssessment",
    "TrustTier",
    "classify_outcome",
    "classify_rung_outcome",
    "has_assumption_markers",
    "normalize_sql_for_match",
    "reconcile_outcome_metric",
    "reconcile_prose_numbers",
    "strip_sql_literals_and_comments",
    "tokenize_googlesql",
]


class TrustTier(str, Enum):
    """3-Tier Trust classification hierarchy for analytical outputs."""

    TIER_3_REVIEW_REQUIRED = "TIER_3_REVIEW_REQUIRED"
    TIER_2_GROUNDED = "TIER_2_GROUNDED"
    TIER_1_VERIFIED_OR_COMPILED = "TIER_1_VERIFIED_OR_COMPILED"


class TokenType(Enum):
    """Lexical token kinds for GoogleSQL and ISO GQL statements."""

    WHITESPACE = auto()
    COMMENT = auto()
    STRING = auto()
    BACKTICK = auto()
    IDENT = auto()
    NUMBER = auto()
    PUNCT = auto()


@dataclass(frozen=True)
class Token:
    """Single lexical token with span offsets."""

    type: TokenType
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class TrustAssessment:
    """Result of stateless 3-tier trust classification and numeric reconciliation."""

    tier: TrustTier
    sub_mode: str
    reasons: tuple[str, ...] = ()
    normalized_sql: str = ""
    uses_graph_table: bool = False
    uses_graph_expand: bool = False
    uses_measure: bool = False


_ASSUMPTION_PATTERN = re.compile(
    r"\b(i\s+assumed|i\s+have\s+assumed|assuming|under\s+the\s+assumption|by\s+assuming)\b",
    re.IGNORECASE,
)

_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"("
    r"(?:[-+][$€£]|[$€£][-+]|[-+]|[$€£])?[ \t]*"
    r"((\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?:[ \t]*(%)|([A-Za-z%]+))?"
    r")"
    r"(?![A-Za-z0-9_])"
)

_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_MONTH_NAME_DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
    re.IGNORECASE,
)
_BENIGN_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:Q[1-4]|H[1-2]|FY\d{2,4}|v\d+(?:\.\d+)*|R[1-9][0-9]*)\b",
    re.IGNORECASE,
)
_SCIENTIFIC_NOTATION_PATTERN = re.compile(r"\b\d+(?:\.\d+)?[eE][+-]?\d+\b")
_UNDERSCORE_NUMBER_PATTERN = re.compile(r"\b\d+_\d+(?:_\d+)*\b")
_ROW_COUNT_NOUN_PATTERN = re.compile(r"^(?:of\s+)?(rows?|records?|results?)\b", re.IGNORECASE)
_ISO_CURRENCY_CODES = frozenset({"usd", "sgd", "eur", "gbp", "jpy", "aud", "cad"})

_TIER_1_MECHANISM_MARKERS = (
    "verified query",
    "semantic contract",
    "measure(",
    "property graph",
    "iso gql",
    "graph_table",
    "data product",
    "certified",
    "row access",
    "rls",
    "sla_overlay",
    "sla overlay",
    "contract extraction",
    "compiled",
    "docai",
    "ai.generate",
)


def tokenize_googlesql(sql: str) -> list[Token]:
    """Scans GoogleSQL / ISO GQL text into tokens while preserving literals verbatim."""
    tokens: list[Token] = []
    n = len(sql)
    i = 0

    while i < n:
        ch = sql[i]

        if ch.isspace():
            start = i
            while i < n and sql[i].isspace():
                i += 1
            tokens.append(Token(TokenType.WHITESPACE, sql[start:i], start, i))
            continue

        if (ch == "-" and i + 1 < n and sql[i + 1] == "-") or ch == "#":
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            if i < n and sql[i] == "\n":
                i += 1
            tokens.append(Token(TokenType.COMMENT, sql[start:i], start, i))
            continue

        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            start = i
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i = i + 2 if i + 1 < n else n
            tokens.append(Token(TokenType.COMMENT, sql[start:i], start, i))
            continue

        is_raw = False
        quote_start = i
        if ch in ("r", "R") and i + 1 < n and sql[i + 1] in ("'", '"'):
            is_raw = True
            quote_start = i + 1

        if sql[quote_start] in ("'", '"'):
            start = i
            qchar = sql[quote_start]
            is_triple = quote_start + 2 < n and sql[quote_start : quote_start + 3] == qchar * 3
            if is_triple:
                delimiter = qchar * 3
                i = quote_start + 3
                while i < n:
                    if sql[i : i + 3] == delimiter:
                        i += 3
                        break
                    if not is_raw and sql[i] == "\\":
                        i += 2
                    else:
                        i += 1
            else:
                i = quote_start + 1
                while i < n:
                    if sql[i] == qchar:
                        if i + 1 < n and sql[i + 1] == qchar and i > quote_start + 1:
                            i += 2
                            continue
                        i += 1
                        break
                    if not is_raw and sql[i] == "\\":
                        i += 2
                    else:
                        i += 1
            tokens.append(Token(TokenType.STRING, sql[start:i], start, i))
            continue

        if ch == "`":
            start = i
            i += 1
            while i < n:
                if sql[i] == "`":
                    i += 1
                    break
                if sql[i] == "\\":
                    i += 2
                else:
                    i += 1
            tokens.append(Token(TokenType.BACKTICK, sql[start:i], start, i))
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            tokens.append(Token(TokenType.IDENT, sql[start:i], start, i))
            continue

        if ch.isdigit():
            start = i
            while i < n and sql[i].isdigit():
                i += 1
            if i < n and sql[i] == "." and (i + 1 == n or sql[i + 1] != "."):
                i += 1
                while i < n and sql[i].isdigit():
                    i += 1
            if i < n and sql[i] in ("e", "E"):
                i += 1
                if i < n and sql[i] in ("+", "-"):
                    i += 1
                while i < n and sql[i].isdigit():
                    i += 1
            tokens.append(Token(TokenType.NUMBER, sql[start:i], start, i))
            continue

        tokens.append(Token(TokenType.PUNCT, ch, i, i + 1))
        i += 1

    return tokens


def strip_sql_literals_and_comments(sql: str) -> str:
    """Replaces string literals and comments with spaces while keeping structure intact."""
    if not sql:
        return ""
    tokens = tokenize_googlesql(sql)
    chunks: list[str] = []
    for tok in tokens:
        if tok.type in (TokenType.STRING, TokenType.COMMENT):
            chunks.append(" ")
        else:
            chunks.append(tok.text)
    return "".join(chunks)


def normalize_sql_for_match(sql: str | None) -> str:
    """Normalizes SQL/GQL outside literals while preserving string literals verbatim."""
    if not sql:
        return ""

    tokens = tokenize_googlesql(sql)
    out_parts: list[str] = []
    pending_space = False

    for tok in tokens:
        if tok.type in (TokenType.WHITESPACE, TokenType.COMMENT):
            if out_parts:
                pending_space = True
            continue

        if pending_space:
            out_parts.append(" ")
            pending_space = False

        if tok.type == TokenType.STRING:
            out_parts.append(tok.text)
        elif tok.type == TokenType.BACKTICK:
            inner = tok.text[1:-1] if len(tok.text) >= 2 and tok.text.endswith("`") else tok.text
            out_parts.append(inner.lower())
        else:
            out_parts.append(tok.text.lower())

    normalized = "".join(out_parts).strip()
    while normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    return normalized


def has_assumption_markers(prose: str) -> bool:
    """Returns True if prose contains explicit assumption markers."""
    return bool(_ASSUMPTION_PATTERN.search(prose or ""))


def _to_float(val: Any) -> float | None:
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float, Decimal)):
        num = float(val)
        return None if (math.isnan(num) or math.isinf(num)) else num
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            num = float(cleaned)
            return None if (math.isnan(num) or math.isinf(num)) else num
        except ValueError:
            return None
    return None


def reconcile_prose_numbers(
    prose: str,
    *,
    question: str = "",
    result_rows: Sequence[Mapping[str, Any]] = (),
    expected_values: Sequence[float | int] = (),
) -> tuple[str, ...]:
    """Audits numeric tokens in prose against query result rows and question echoes."""
    if not prose:
        return ()

    clean = prose.replace("\u2212", "-")
    question_clean = (question or "").replace("\u2212", "-")

    clean = re.sub(r"```[\s\S]*?```", " ", clean)
    clean = re.sub(r"`[^`]*`", " ", clean)
    clean = re.sub(r"(?m)^\s*\d+[.)]\s+", " ", clean)
    clean = re.sub(r"(?m)^\s*[-*+]\s+", " ", clean)

    valid_dates: set[str] = set(_ISO_DATE_PATTERN.findall(question_clean))
    for match in _MONTH_NAME_DATE_PATTERN.finditer(question_clean):
        valid_dates.add(match.group(0))

    for row in result_rows:
        for val in row.values():
            if isinstance(val, str):
                valid_dates.update(_ISO_DATE_PATTERN.findall(val))
                for m_match in _MONTH_NAME_DATE_PATTERN.finditer(val):
                    valid_dates.add(m_match.group(0))

    for vd in valid_dates:
        clean = clean.replace(vd, " ")

    clean = _BENIGN_IDENTIFIER_PATTERN.sub(" ", clean)
    unverified: list[str] = []

    for sn_match in _SCIENTIFIC_NOTATION_PATTERN.finditer(clean):
        unverified.append(sn_match.group(0))
    clean = _SCIENTIFIC_NOTATION_PATTERN.sub(" ", clean)

    for us_match in _UNDERSCORE_NUMBER_PATTERN.finditer(clean):
        unverified.append(us_match.group(0))
    clean = _UNDERSCORE_NUMBER_PATTERN.sub(" ", clean)

    clean = re.sub(
        r"(?<![-+.$€£\d])(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?!\.\d|\d)",
        r"\1 to \2",
        clean,
    )
    clean = re.sub(
        r"(?<![-+.$€£\d])(\d+(?:\.\d+)?)[ \t]+-[ \t]+(\d+(?:\.\d+)?)(?!\.\d|\d)",
        r"\1 to \2",
        clean,
    )

    question_years: set[float] = set()
    for ym in re.finditer(r"(?<![A-Za-z0-9_])(\d{4})(?![A-Za-z0-9_])", question_clean):
        y_val = float(ym.group(1))
        if 1900 <= y_val <= 2100:
            question_years.add(y_val)

    question_limit_numbers: set[float] = set()
    for lm in re.finditer(r"\b(?:top|first|last|limit)\s+(\d+)\b", question_clean, flags=re.IGNORECASE):
        question_limit_numbers.add(float(lm.group(1)))

    cell_numbers: list[float] = []
    for row in result_rows:
        for val in row.values():
            num = _to_float(val)
            if num is not None:
                cell_numbers.append(num)
    for exp_val in expected_values:
        num = _to_float(exp_val)
        if num is not None:
            cell_numbers.append(num)

    for match in _NUMERIC_TOKEN_PATTERN.finditer(clean):
        raw_token = match.group(1).strip()
        num_str = match.group(2).replace(",", "")
        is_negative = "-" in match.group(1)
        suffix = match.group(4) or match.group(5) or ""
        has_currency = any(c in raw_token for c in ("$", "€", "£"))

        if suffix and suffix.lower() in _ISO_CURRENCY_CODES:
            has_currency = True
            suffix = ""

        has_currency_or_suffix = has_currency or bool(suffix)

        try:
            abs_val = float(num_str)
            token_val = -abs_val if is_negative else abs_val
        except ValueError:
            continue

        if suffix not in ("", "%", "k", "K", "m", "M", "b", "B"):
            unverified.append(raw_token)
            continue

        if not has_currency_or_suffix:
            if 1900 <= int(abs_val) <= 2100 and token_val in question_years and "." not in num_str and not is_negative:
                continue
            if token_val in question_limit_numbers and not is_negative and "." not in num_str:
                prefix_context = clean[max(0, match.start() - 20) : match.end()]
                if re.search(rf"\b(?:top|first|last|limit)\s+{re.escape(num_str)}\b", prefix_context, re.IGNORECASE):
                    continue

        remainder = clean[match.end() : match.end() + 20].strip()
        if (
            not has_currency_or_suffix
            and not is_negative
            and "." not in num_str
            and _ROW_COUNT_NOUN_PATTERN.match(remainder)
        ):
            if len(result_rows) >= 1 and math.isclose(token_val, float(len(result_rows)), abs_tol=1e-6):
                continue

        decimals = len(num_str.split(".")[1]) if "." in num_str else 0
        if suffix == "%":
            scales: tuple[float, ...] = (1.0, 0.01)
        elif suffix in ("k", "K"):
            scales = (1000.0,)
        elif suffix in ("m", "M"):
            scales = (1_000_000.0,)
        elif suffix in ("b", "B"):
            scales = (1_000_000_000.0,)
        else:
            scales = (1.0,)

        matched = False
        for scale in scales:
            nominal_val = token_val * scale
            if decimals > 0 or scale != 1.0 or suffix == "%":
                tol = 0.5 * (10**-decimals) * scale + 1e-6
                if any(abs(c - nominal_val) <= tol for c in cell_numbers):
                    matched = True
                    break
            else:
                for c in cell_numbers:
                    tol = 1e-6 if c.is_integer() else 0.5
                    if abs(c - nominal_val) <= tol:
                        matched = True
                        break
            if matched:
                break

        if not matched:
            unverified.append(raw_token)

    return tuple(unverified)


def reconcile_outcome_metric(
    expected_value: float | int,
    result_rows: Sequence[Mapping[str, Any]],
    *,
    abs_tol: float = 0.01,
) -> tuple[bool, float | None, str]:
    """Reconciles an expected numeric metric against returned BigQuery result rows."""
    target = _to_float(expected_value)
    if target is None:
        return False, None, "invalid_expected_value"
    if not result_rows:
        return False, None, "empty_result_rows"

    candidates: list[float] = []
    col_sums: dict[str, float] = {}

    for row in result_rows:
        for col, raw in row.items():
            num = _to_float(raw)
            if num is not None:
                candidates.append(num)
                col_sums[col] = col_sums.get(col, 0.0) + num

    for val in candidates:
        if abs(val - target) <= abs_tol:
            return True, val, "direct_cell_match"

    for col_sum in col_sums.values():
        if abs(col_sum - target) <= abs_tol:
            return True, col_sum, "column_sum_match"

    row_cnt = float(len(result_rows))
    if abs(row_cnt - target) <= abs_tol:
        return True, row_cnt, "row_count_match"

    first_val = candidates[0] if candidates else None
    return False, first_val, f"metric_mismatch:expected={target},actual={first_val}"


def classify_outcome(
    *,
    sql_or_gql: str | None,
    query_language: str = "SQL",
    answer_headline: str = "",
    answer_detail: str = "",
    question: str = "",
    numeric_value: float | int | None = None,
    result_rows: Sequence[Mapping[str, Any]] | None = None,
    context_mechanism: str | None = None,
    context_payload: str | None = None,
    is_blind: bool = False,
    error_retries: int = 0,
    has_verified_query_contract: bool = False,
    strict_prose_reconcile: bool = False,
) -> TrustAssessment:
    """Statelessly classifies an analytical execution into a 3-Tier TrustTier."""
    normalized_sql = normalize_sql_for_match(sql_or_gql)
    stripped_sql = strip_sql_literals_and_comments(sql_or_gql or "")

    uses_graph_table = bool(
        re.search(r"(?<![A-Za-z0-9_`])GRAPH_TABLE\s*\(", stripped_sql, re.IGNORECASE)
    )
    uses_graph_expand = bool(
        re.search(r"(?<![A-Za-z0-9_`])GRAPH_EXPAND\s*\(", stripped_sql, re.IGNORECASE)
    )
    uses_measure = bool(
        re.search(r"(?<![A-Za-z0-9_`])(?:MEASURE|AGG)\s*\(", stripped_sql, re.IGNORECASE)
    )

    reasons: list[str] = []
    if not normalized_sql:
        reasons.append("empty_query")
    if is_blind:
        reasons.append("ungrounded_blind_query")
    if error_retries > 0:
        reasons.append("error_recovery_retry")
    if has_assumption_markers(answer_headline) or has_assumption_markers(answer_detail):
        reasons.append("assumption_marker_present")

    if result_rows is not None:
        if not result_rows:
            reasons.append("empty_result_rows")
        else:
            if numeric_value is not None:
                ok, _, detail = reconcile_outcome_metric(numeric_value, result_rows)
                if not ok:
                    reasons.append(detail)
            headline_clean = re.sub(
                r"\(\s*[+-]?\d+(?:\.\d+)?\s*bps[^)]*\)",
                " ",
                answer_headline,
                flags=re.IGNORECASE,
            )
            unverified_headline = reconcile_prose_numbers(
                headline_clean,
                question=question,
                result_rows=result_rows,
            )
            for token in unverified_headline:
                reasons.append(f"unverified_headline_numeric:{token}")

            if strict_prose_reconcile:
                unverified_detail = reconcile_prose_numbers(
                    answer_detail,
                    question=question,
                    result_rows=result_rows,
                )
                for token in unverified_detail:
                    reasons.append(f"unverified_detail_numeric:{token}")

    if reasons:
        return TrustAssessment(
            tier=TrustTier.TIER_3_REVIEW_REQUIRED,
            sub_mode="REVIEW_REQUIRED",
            reasons=tuple(reasons),
            normalized_sql=normalized_sql,
            uses_graph_table=uses_graph_table,
            uses_graph_expand=uses_graph_expand,
            uses_measure=uses_measure,
        )

    mech_lower = (context_mechanism or "").lower()
    uses_gql = query_language.upper() in ("GQL", "SQL+GQL") or uses_graph_table
    has_tier1_marker = any(marker in mech_lower for marker in _TIER_1_MECHANISM_MARKERS)

    if has_verified_query_contract or uses_measure or uses_gql or uses_graph_expand or has_tier1_marker:
        sub_mode = (
            "GRAPH_MEASURE_COMPILED"
            if (uses_measure or uses_gql or uses_graph_expand)
            else "VERIFIED_OR_CONTRACT_COMPILED"
        )
        return TrustAssessment(
            tier=TrustTier.TIER_1_VERIFIED_OR_COMPILED,
            sub_mode=sub_mode,
            reasons=(),
            normalized_sql=normalized_sql,
            uses_graph_table=uses_graph_table,
            uses_graph_expand=uses_graph_expand,
            uses_measure=uses_measure,
        )

    if (context_payload and context_payload.strip()) or (context_mechanism and context_mechanism.strip()):
        return TrustAssessment(
            tier=TrustTier.TIER_2_GROUNDED,
            sub_mode="SCHEMA_OR_GLOSSARY_GROUNDED",
            reasons=(),
            normalized_sql=normalized_sql,
            uses_graph_table=uses_graph_table,
            uses_graph_expand=uses_graph_expand,
            uses_measure=uses_measure,
        )

    return TrustAssessment(
        tier=TrustTier.TIER_3_REVIEW_REQUIRED,
        sub_mode="UNGROUNDED_QUERY",
        reasons=("missing_governing_context",),
        normalized_sql=normalized_sql,
        uses_graph_table=uses_graph_table,
        uses_graph_expand=uses_graph_expand,
        uses_measure=uses_measure,
    )


def classify_rung_outcome(
    outcome: Mapping[str, Any],
    *,
    mode: str,
    question: str = "",
    result_rows: Sequence[Mapping[str, Any]] | None = None,
    strict_prose_reconcile: bool = False,
) -> TrustAssessment:
    """Classifies a RungSpec blind or governed ExecutionOutcome dict."""
    return classify_outcome(
        sql_or_gql=outcome.get("sql_or_gql"),
        query_language=str(outcome.get("query_language", "SQL")),
        answer_headline=str(outcome.get("answer_headline", "")),
        answer_detail=str(outcome.get("answer_detail", "")),
        question=question,
        numeric_value=outcome.get("numeric_value"),
        result_rows=result_rows,
        context_mechanism=outcome.get("context_mechanism"),
        context_payload=outcome.get("context_payload"),
        is_blind=(mode == "blind"),
        error_retries=int(outcome.get("error_retries", 0) or 0),
        strict_prose_reconcile=strict_prose_reconcile,
    )
