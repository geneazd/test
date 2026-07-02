#!/usr/bin/env python3
"""
data_quality_remediation.py

What it does:
- Reads CSV, TSV, Excel, JSON, or Parquet files
- Standardizes column names
- Trims whitespace from text fields
- Converts common null-like values to blanks / NA
- Removes fully empty rows and columns
- Drops duplicate rows
- Attempts type cleanup for numeric, date, boolean, email, and phone fields
- Optionally applies a JSON rules file for required fields, allowed values, ranges, and regex checks
- Writes a cleaned output file
- Writes a remediation report JSON
- Optionally writes invalid/quarantined rows to a separate file

Basic usage:
    python data_quality_remediation.py input.csv cleaned.csv

With a rules file:
    python data_quality_remediation.py input.csv cleaned.csv --rules rules.json --quarantine invalid_rows.csv

Example rules.json:
{
  "required": ["customer_id", "email"],
  "unique": ["customer_id"],
  "allowed_values": {
    "status": ["active", "inactive", "pending"]
  },
  "ranges": {
    "age": {"min": 0, "max": 120}
  },
  "regex": {
    "email": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"
  },
  "rename_columns": {
    "cust id": "customer_id",
    "e-mail": "email"
  },
  "date_columns": ["created_at", "updated_at"],
  "numeric_columns": ["age", "amount"],
  "boolean_columns": ["is_active"]
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


NULL_LIKE_VALUES = {
    "",
    " ",
    "na",
    "n/a",
    "none",
    "null",
    "nil",
    "nan",
    "nat",
    "-",
    "--",
    "unknown",
    "missing",
    "#n/a",
    "#na",
}


TRUE_VALUES = {"true", "t", "yes", "y", "1", "on"}
FALSE_VALUES = {"false", "f", "no", "n", "0", "off"}


def snake_case(value: str) -> str:
    """Convert a column name to snake_case."""
    value = str(value).strip().lower()
    value = re.sub(r"[^\w\s]+", " ", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def make_unique_columns(columns: List[str]) -> List[str]:
    """Ensure duplicate column names are made unique."""
    counts: Dict[str, int] = {}
    result = []

    for column in columns:
        base = column or "unnamed_column"
        if base not in counts:
            counts[base] = 0
            result.append(base)
        else:
            counts[base] += 1
            result.append(f"{base}_{counts[base]}")

    return result


def load_rules(path: Optional[Path]) -> Dict[str, Any]:
    """Load optional remediation/validation rules from JSON."""
    if not path:
        return {}

    if not path.exists():
        raise FileNotFoundError(f"Rules file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        rules = json.load(file)

    if not isinstance(rules, dict):
        raise ValueError("Rules file must contain a JSON object.")

    return rules


def read_data(path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """Read a supported data file."""
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path, dtype="object", keep_default_na=False)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", dtype="object", keep_default_na=False)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet_name or 0, dtype="object", keep_default_na=False)
    if suffix == ".json":
        return pd.read_json(path, dtype=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(
        f"Unsupported input format: {suffix}. "
        "Supported formats: .csv, .tsv, .xlsx, .xls, .json, .parquet"
    )


def write_data(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to a supported output file."""
    suffix = path.suffix.lower()

    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix == ".tsv":
        df.to_csv(path, index=False, sep="\t")
        return
    if suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
        return
    if suffix == ".json":
        df.to_json(path, orient="records", indent=2, date_format="iso")
        return
    if suffix == ".parquet":
        df.to_parquet(path, index=False)
        return

    raise ValueError(
        f"Unsupported output format: {suffix}. "
        "Supported formats: .csv, .tsv, .xlsx, .xls, .json, .parquet"
    )


def standardize_columns(df: pd.DataFrame, rules: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Rename columns using optional explicit mappings, then snake_case everything."""
    original_columns = list(df.columns)
    rename_map_from_rules = rules.get("rename_columns", {}) or {}

    normalized_mapping: Dict[str, str] = {}
    new_columns = []

    for original in original_columns:
        original_text = str(original).strip()
        mapped = rename_map_from_rules.get(original_text, rename_map_from_rules.get(original_text.lower(), original_text))
        normalized = snake_case(mapped)
        normalized_mapping[original_text] = normalized
        new_columns.append(normalized)

    df = df.copy()
    df.columns = make_unique_columns(new_columns)
    return df, normalized_mapping


def normalize_nulls_and_whitespace(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Trim text and normalize null-like values to pandas NA."""
    df = df.copy()
    changed_cells = 0

    for column in df.columns:
        before = df[column].copy()

        def clean_cell(value: Any) -> Any:
            if pd.isna(value):
                return pd.NA

            if isinstance(value, str):
                trimmed = value.strip()
                if trimmed.lower() in NULL_LIKE_VALUES:
                    return pd.NA
                return trimmed

            return value

        df[column] = df[column].map(clean_cell)

        changed_cells += int((before.astype(str) != df[column].astype(str)).sum())

    return df, changed_cells


def coerce_numeric_columns(df: pd.DataFrame, columns: List[str]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Coerce specified columns to numeric where possible."""
    df = df.copy()
    failures: Dict[str, int] = {}

    for column in columns:
        if column not in df.columns:
            continue

        original_non_null = df[column].notna()
        cleaned = (
            df[column]
            .astype("string")
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )

        coerced = pd.to_numeric(cleaned, errors="coerce")
        failed = int((original_non_null & coerced.isna()).sum())
        failures[column] = failed
        df[column] = coerced

    return df, failures


def coerce_date_columns(df: pd.DataFrame, columns: List[str]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Coerce specified columns to ISO date strings."""
    df = df.copy()
    failures: Dict[str, int] = {}

    for column in columns:
        if column not in df.columns:
            continue

        original_non_null = df[column].notna()
        coerced = pd.to_datetime(df[column], errors="coerce", utc=False)
        failed = int((original_non_null & coerced.isna()).sum())
        failures[column] = failed
        df[column] = coerced.dt.strftime("%Y-%m-%d")

    return df, failures


def coerce_boolean_columns(df: pd.DataFrame, columns: List[str]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Coerce specified columns to boolean where possible."""
    df = df.copy()
    failures: Dict[str, int] = {}

    for column in columns:
        if column not in df.columns:
            continue

        def convert(value: Any) -> Any:
            if pd.isna(value):
                return pd.NA

            text = str(value).strip().lower()
            if text in TRUE_VALUES:
                return True
            if text in FALSE_VALUES:
                return False
            return pd.NA

        original_non_null = df[column].notna()
        coerced = df[column].map(convert)
        failures[column] = int((original_non_null & coerced.isna()).sum())
        df[column] = coerced

    return df, failures


def standardize_email_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Lowercase and lightly validate likely email columns."""
    df = df.copy()
    invalid_counts: Dict[str, int] = {}
    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    for column in df.columns:
        if "email" not in column:
            continue

        df[column] = df[column].map(lambda x: x.lower() if isinstance(x, str) else x)
        invalid = df[column].dropna().map(lambda x: not bool(email_regex.match(str(x))))
        invalid_counts[column] = int(invalid.sum())

    return df, invalid_counts


def standardize_phone_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize likely phone columns to digits plus optional leading plus."""
    df = df.copy()

    for column in df.columns:
        if "phone" not in column and "mobile" not in column:
            continue

        def clean_phone(value: Any) -> Any:
            if pd.isna(value):
                return pd.NA

            text = str(value).strip()
            leading_plus = text.startswith("+")
            digits = re.sub(r"\D", "", text)

            if not digits:
                return pd.NA

            return f"+{digits}" if leading_plus else digits

        df[column] = df[column].map(clean_phone)

    return df


def validate_rows(df: pd.DataFrame, rules: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Validate rows using rules and return:
    - valid/clean rows
    - invalid/quarantined rows with dq_errors column
    - validation summary
    """
    errors_by_index: Dict[Any, List[str]] = {idx: [] for idx in df.index}

    required = rules.get("required", []) or []
    for column in required:
        if column not in df.columns:
            for idx in df.index:
                errors_by_index[idx].append(f"missing_required_column:{column}")
            continue

        missing_mask = df[column].isna() | (df[column].astype("string").str.strip() == "")
        for idx in df.index[missing_mask]:
            errors_by_index[idx].append(f"missing_required_value:{column}")

    allowed_values = rules.get("allowed_values", {}) or {}
    for column, values in allowed_values.items():
        if column not in df.columns:
            continue

        allowed_set = {str(value).lower() for value in values}
        invalid_mask = df[column].notna() & ~df[column].astype("string").str.lower().isin(allowed_set)
        for idx in df.index[invalid_mask]:
            errors_by_index[idx].append(f"invalid_allowed_value:{column}")

    ranges = rules.get("ranges", {}) or {}
    for column, range_rule in ranges.items():
        if column not in df.columns:
            continue

        numeric = pd.to_numeric(df[column], errors="coerce")
        min_value = range_rule.get("min")
        max_value = range_rule.get("max")

        invalid_mask = pd.Series(False, index=df.index)
        if min_value is not None:
            invalid_mask |= numeric < min_value
        if max_value is not None:
            invalid_mask |= numeric > max_value

        invalid_mask &= df[column].notna()
        for idx in df.index[invalid_mask]:
            errors_by_index[idx].append(f"out_of_range:{column}")

    regex_rules = rules.get("regex", {}) or {}
    for column, pattern in regex_rules.items():
        if column not in df.columns:
            continue

        compiled = re.compile(pattern)
        invalid_mask = df[column].notna() & ~df[column].astype("string").map(lambda x: bool(compiled.match(x)))
        for idx in df.index[invalid_mask]:
            errors_by_index[idx].append(f"regex_failed:{column}")

    unique_columns = rules.get("unique", []) or []
    for column in unique_columns:
        if column not in df.columns:
            continue

        duplicate_mask = df[column].notna() & df.duplicated(subset=[column], keep=False)
        for idx in df.index[duplicate_mask]:
            errors_by_index[idx].append(f"not_unique:{column}")

    error_counts: Dict[str, int] = {}
    for error_list in errors_by_index.values():
        for error in error_list:
            error_counts[error] = error_counts.get(error, 0) + 1

    invalid_indexes = [idx for idx, errors in errors_by_index.items() if errors]
    invalid_df = df.loc[invalid_indexes].copy()
    if not invalid_df.empty:
        invalid_df["dq_errors"] = ["; ".join(errors_by_index[idx]) for idx in invalid_indexes]

    valid_df = df.drop(index=invalid_indexes).copy()

    summary = {
        "invalid_row_count": int(len(invalid_df)),
        "valid_row_count": int(len(valid_df)),
        "error_counts": error_counts,
    }

    return valid_df, invalid_df, summary


def remediate(
    input_path: Path,
    output_path: Path,
    report_path: Path,
    rules_path: Optional[Path],
    quarantine_path: Optional[Path],
    sheet_name: Optional[str],
    keep_invalid: bool,
) -> Dict[str, Any]:
    """Run the full remediation workflow."""
    rules = load_rules(rules_path)
    df = read_data(input_path, sheet_name=sheet_name)

    report: Dict[str, Any] = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "output_file": str(output_path),
        "initial_row_count": int(len(df)),
        "initial_column_count": int(len(df.columns)),
        "actions": {},
    }

    df, column_mapping = standardize_columns(df, rules)
    report["actions"]["column_standardization"] = {
        "original_to_standardized": column_mapping,
        "final_columns": list(df.columns),
    }

    before_rows = len(df)
    before_columns = len(df.columns)
    df, changed_cells = normalize_nulls_and_whitespace(df)
    report["actions"]["null_and_whitespace_cleanup"] = {
        "changed_cells": changed_cells,
    }

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    report["actions"]["empty_rows_and_columns_removed"] = {
        "empty_rows_removed": int(before_rows - len(df)),
        "empty_columns_removed": int(before_columns - len(df.columns)),
    }

    duplicate_rows_before = len(df)
    df = df.drop_duplicates()
    report["actions"]["duplicate_rows_removed"] = int(duplicate_rows_before - len(df))

    numeric_columns = [snake_case(c) for c in rules.get("numeric_columns", []) or []]
    date_columns = [snake_case(c) for c in rules.get("date_columns", []) or []]
    boolean_columns = [snake_case(c) for c in rules.get("boolean_columns", []) or []]

    df, numeric_failures = coerce_numeric_columns(df, numeric_columns)
    df, date_failures = coerce_date_columns(df, date_columns)
    df, boolean_failures = coerce_boolean_columns(df, boolean_columns)

    report["actions"]["type_coercion"] = {
        "numeric_conversion_failures": numeric_failures,
        "date_conversion_failures": date_failures,
        "boolean_conversion_failures": boolean_failures,
    }

    df, email_invalid_counts = standardize_email_columns(df)
    df = standardize_phone_columns(df)
    report["actions"]["contact_field_cleanup"] = {
        "likely_email_columns_invalid_count": email_invalid_counts,
        "likely_phone_columns_normalized": [
            column for column in df.columns if "phone" in column or "mobile" in column
        ],
    }

    valid_df, invalid_df, validation_summary = validate_rows(df, rules)
    report["validation"] = validation_summary

    output_df = df if keep_invalid else valid_df
    write_data(output_df, output_path)

    if quarantine_path:
        write_data(invalid_df, quarantine_path)
        report["quarantine_file"] = str(quarantine_path)

    report["final_row_count"] = int(len(output_df))
    report["final_column_count"] = int(len(output_df.columns))

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean, standardize, validate, and remediate tabular data files."
    )

    parser.add_argument("input", help="Input file path: .csv, .tsv, .xlsx, .xls, .json, or .parquet")
    parser.add_argument("output", help="Cleaned output file path")
    parser.add_argument(
        "--rules",
        help="Optional JSON rules file for validation and column-specific remediation",
    )
    parser.add_argument(
        "--report",
        help="Optional report path. Defaults to <output_stem>_dq_report.json",
    )
    parser.add_argument(
        "--quarantine",
        help="Optional path for invalid/quarantined rows",
    )
    parser.add_argument(
        "--sheet-name",
        help="Excel sheet name. Defaults to first sheet.",
    )
    parser.add_argument(
        "--keep-invalid",
        action="store_true",
        help="Keep invalid rows in the cleaned output. By default, invalid rows are excluded when rules are provided.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    rules_path = Path(args.rules).expanduser().resolve() if args.rules else None
    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else output_path.with_name(f"{output_path.stem}_dq_report.json")
    )
    quarantine_path = Path(args.quarantine).expanduser().resolve() if args.quarantine else None

    try:
        report = remediate(
            input_path=input_path,
            output_path=output_path,
            report_path=report_path,
            rules_path=rules_path,
            quarantine_path=quarantine_path,
            sheet_name=args.sheet_name,
            keep_invalid=args.keep_invalid,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("Data quality remediation complete.")
    print(f"Cleaned file: {output_path}")
    print(f"Report file: {report_path}")

    if quarantine_path:
        print(f"Quarantine file: {quarantine_path}")

    print(
        json.dumps(
            {
                "initial_rows": report["initial_row_count"],
                "final_rows": report["final_row_count"],
                "invalid_rows": report.get("validation", {}).get("invalid_row_count", 0),
                "duplicate_rows_removed": report.get("actions", {}).get("duplicate_rows_removed", 0),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
