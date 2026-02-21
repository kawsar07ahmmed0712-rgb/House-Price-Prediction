from __future__ import annotations

import ast
import base64
import html
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "House-Price.ipynb"
WEB_ROOT = PROJECT_ROOT / "web"
CHARTS_DIR = WEB_ROOT / "assets" / "charts"
DATA_DIR = WEB_ROOT / "assets" / "data"
JS_DIR = WEB_ROOT / "assets" / "js"
PROFILE_PATH_CANDIDATES = [
    PROJECT_ROOT / "ames_house_prices_profile.html",
    PROJECT_ROOT / "house_profile_compact.html",
]


NON_ASCII = re.compile(r"[^\x00-\x7F]+")


CHART_CELL_MAP: dict[int, str] = {
    15: "saleprice_distribution.png",
    17: "qq_raw_vs_log.png",
    18: "saleprice_log_distribution.png",
    25: "saleprice_iqr_boxplots.png",
    29: "missingness_heatmap_top20.png",
    31: "correlation_heatmap_full.png",
    37: "top3_scatter_raw.png",
    39: "top3_scatter_log.png",
    41: "overallqual_vs_saleprice.png",
    43: "overallqual_vs_log_saleprice.png",
    48: "top15_neighborhood_mean.png",
}


def ensure_dirs() -> None:
    for path in (CHARTS_DIR, DATA_DIR, JS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def find_profile_path() -> Path | None:
    for candidate in PROFILE_PATH_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def load_notebook(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize_text(text: str) -> str:
    return NON_ASCII.sub("", text)


def as_text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def parse_number(value: str) -> float | int | None:
    value = value.strip().replace(",", "")
    if not value:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return None


def parse_size_to_bytes(value: str) -> float | None:
    clean = value.strip().replace(",", "")
    match = re.match(r"^([\d.]+)\s*([KMGT]?i?B)$", clean, re.I)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).upper()
    factor_map = {
        "B": 1,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
    }
    factor = factor_map.get(unit)
    if factor is None:
        return None
    return amount * factor


def get_cell(nb: dict[str, Any], index: int) -> dict[str, Any]:
    return nb["cells"][index]


def get_stream_text(cell: dict[str, Any]) -> str:
    chunks: list[str] = []
    for output in cell.get("outputs", []):
        if output.get("output_type") == "stream":
            chunks.append(as_text(output.get("text", "")))
    return normalize_text("".join(chunks))


def get_first_text_plain(cell: dict[str, Any]) -> str:
    for output in cell.get("outputs", []):
        data = output.get("data")
        if isinstance(data, dict) and "text/plain" in data:
            return normalize_text(as_text(data["text/plain"]))
    return ""


def parse_int(value: str) -> int:
    return int(value.replace(",", "").strip())


def parse_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def parse_shape(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"Shape:\s*([\d,]+)\s*rows.*?([\d,]+)\s*columns", text, re.S)
    if not match:
        return None, None
    return parse_int(match.group(1)), parse_int(match.group(2))


def parse_feature_counts(text: str) -> tuple[int | None, int | None]:
    num_match = re.search(r"Numerical features \((\d+)\)", text)
    cat_match = re.search(r"Categorical features \((\d+)\)", text)
    numeric = int(num_match.group(1)) if num_match else None
    categorical = int(cat_match.group(1)) if cat_match else None
    return numeric, categorical


def parse_target_stats(text: str) -> dict[str, float | None]:
    values = {
        "mean_saleprice": None,
        "median_saleprice": None,
        "saleprice_skew": None,
        "saleprice_kurtosis": None,
    }
    patterns = {
        "mean_saleprice": r"Mean\s*:\s*([\d,\.]+)",
        "median_saleprice": r"Median\s*:\s*([\d,\.]+)",
        "saleprice_skew": r"Skewness\s*:\s*([\d,\.]+)",
        "saleprice_kurtosis": r"Kurtosis\s*:\s*([\d,\.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            values[key] = parse_float(match.group(1))
    return values


def parse_iqr_bounds(text: str) -> dict[str, float | None]:
    values = {
        "q1": None,
        "q3": None,
        "iqr_value": None,
        "iqr_lower_bound": None,
        "iqr_upper_bound": None,
    }
    patterns = {
        "q1": r"Q1\s*:\s*([\d,\.]+)",
        "q3": r"Q3\s*:\s*([\d,\.]+)",
        "iqr_value": r"IQR\s*:\s*([\d,\.]+)",
        "iqr_lower_bound": r"Lower bound:\s*([\d,\.]+)",
        "iqr_upper_bound": r"Upper bound:\s*([\d,\.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            values[key] = parse_float(match.group(1))
    return values


def parse_iqr_row_counts(text: str) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {
        "rows_before_iqr": None,
        "rows_after_iqr": None,
        "rows_removed_iqr": None,
        "rows_removed_pct_iqr": None,
    }
    patterns = {
        "rows_before_iqr": r"Rows before IQR filtering\s*:\s*([\d,]+)",
        "rows_after_iqr": r"Rows after IQR filtering\s*:\s*([\d,]+)",
        "rows_removed_iqr": r"Rows removed as outliers\s*:\s*([\d,]+)",
        "rows_removed_pct_iqr": r"% removed:\s*([\d\.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            if key == "rows_removed_pct_iqr":
                values[key] = parse_float(match.group(1))
            else:
                values[key] = parse_int(match.group(1))
    return values


def parse_correlation_table(text: str) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or "Correlation with SalePrice" in line:
            continue
        match = re.match(r"^(.+?)\s+(-?\d+(?:\.\d+)?)$", line.strip())
        if match:
            rows.append(
                {
                    "feature": match.group(1).strip(),
                    "correlation": parse_float(match.group(2)),
                }
            )
    return rows


def parse_driver_list(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        parsed = ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return []
    return [str(item) for item in parsed]


def parse_neighborhood_table(text: str) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("mean") or line.startswith("Neighborhood"):
            continue
        match = re.match(
            r"^(\S+)\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s+(\d+)$",
            line,
        )
        if match:
            rows.append(
                {
                    "neighborhood": match.group(1),
                    "mean_saleprice": parse_float(match.group(2)),
                    "median_saleprice": parse_float(match.group(3)),
                    "count": int(match.group(4)),
                }
            )
    return rows


def parse_missing_table(
    text: str, rows_after_iqr: int | None
) -> list[dict[str, float | int | str | None]]:
    rows: list[dict[str, float | int | str | None]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("dtype:"):
            continue
        match = re.match(r"^([A-Za-z0-9_]+)\s+(\d+)$", line)
        if match:
            count = int(match.group(2))
            missing_pct = None
            if rows_after_iqr and rows_after_iqr > 0:
                missing_pct = round((count / rows_after_iqr) * 100, 2)
            rows.append(
                {
                    "feature": match.group(1),
                    "missing_count": count,
                    "missing_pct": missing_pct,
                }
            )
    return rows


def extract_png_from_cell(cell: dict[str, Any]) -> bytes | None:
    for output in cell.get("outputs", []):
        data = output.get("data")
        if isinstance(data, dict) and "image/png" in data:
            encoded = as_text(data["image/png"]).replace("\n", "")
            return base64.b64decode(encoded)
    return None


def export_charts(nb: dict[str, Any]) -> dict[str, str]:
    chart_files: dict[str, str] = {}
    for cell_index, filename in CHART_CELL_MAP.items():
        image_bytes = extract_png_from_cell(get_cell(nb, cell_index))
        if image_bytes is None:
            continue
        output_path = CHARTS_DIR / filename
        output_path.write_bytes(image_bytes)
        chart_files[filename.replace(".png", "")] = f"assets/charts/{filename}"

    source_mockup = PROJECT_ROOT / "image.png"
    if source_mockup.exists():
        target_mockup = CHARTS_DIR / "dashboard_mockup.png"
        shutil.copy2(source_mockup, target_mockup)
        chart_files["dashboard_mockup"] = "assets/charts/dashboard_mockup.png"
    return chart_files


def parse_table_rows_from_block(block: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for key_html, val_html in re.findall(r"<tr><th>(.*?)<td[^>]*>(.*?)(?=<tr>|$)", block, re.S):
        key = strip_tags(key_html).lower().replace(" ", "_").replace("(%)", "pct")
        value = strip_tags(val_html)
        rows[key] = value
    return rows


def parse_alert_rows(alert_block: str) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    pattern = re.compile(
        r"<tr><td><a href=#pp_var_[^>]+><code>(.*?)</code></a>\s*(.*?)<td><span class=\"badge [^\"]+\">(.*?)</span>",
        re.S,
    )
    for feature_html, message_html, alert_type_html in pattern.findall(alert_block):
        feature = strip_tags(feature_html)
        message = strip_tags(message_html)
        alert_type = strip_tags(alert_type_html)
        alerts.append(
            {
                "feature": feature,
                "message": message,
                "type": alert_type,
            }
        )
    return alerts


def parse_missing_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    if alert.get("type") != "Missing":
        return None
    match = re.search(r"has\s+([\d,]+)\s+\(([\d\.]+)%\)\s+missing values", alert["message"])
    if not match:
        return None
    return {
        "feature": alert["feature"],
        "missing_count": parse_int(match.group(1)),
        "missing_pct": parse_float(match.group(2)),
        "message": alert["message"],
    }


def parse_zero_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    if alert.get("type") != "Zeros":
        return None
    match = re.search(r"has\s+([\d,]+)\s+\(([\d\.]+)%\)\s+zeros", alert["message"])
    if not match:
        return None
    return {
        "feature": alert["feature"],
        "zero_count": parse_int(match.group(1)),
        "zero_pct": parse_float(match.group(2)),
        "message": alert["message"],
    }


def parse_imbalance_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    if alert.get("type") != "Imbalance":
        return None
    match = re.search(r"\(([\d\.]+)%\)", alert["message"])
    if not match:
        return None
    return {
        "feature": alert["feature"],
        "dominant_pct": parse_float(match.group(1)),
        "message": alert["message"],
    }


def parse_profile_report(path: Path) -> dict[str, Any]:
    text = load_text(path)

    meta_date_match = re.search(r"<meta content=\"([^\"]+)\" name=date>", text)
    report_date = meta_date_match.group(1) if meta_date_match else None

    stats_block_match = re.search(
        r"Dataset statistics<table class=\"table table-striped\"><tbody>(.*?)</table>",
        text,
        re.S,
    )
    stats_raw = parse_table_rows_from_block(stats_block_match.group(1)) if stats_block_match else {}

    type_block_match = re.search(
        r"Variable types<table class=\"table table-striped\"><tbody>(.*?)</table>",
        text,
        re.S,
    )
    var_types_raw = parse_table_rows_from_block(type_block_match.group(1)) if type_block_match else {}

    alert_count_match = re.search(
        r"Alerts <span class=\"badge text-bg-secondary align-text-top\">(\d+)</span>",
        text,
    )
    alert_count = int(alert_count_match.group(1)) if alert_count_match else 0

    alert_table_match = re.search(
        r"<p class=\"h4 item-header\">Alerts</p>(.*?)</table></div></div></div><div class=\"tab-pane fade\" aria-labelledby=tab-pane-overview-reproduction",
        text,
        re.S,
    )
    alert_rows = parse_alert_rows(alert_table_match.group(1)) if alert_table_match else []
    alert_type_counts = dict(Counter(alert["type"] for alert in alert_rows))

    missing_alerts = [row for row in (parse_missing_alert(a) for a in alert_rows) if row]
    missing_alerts.sort(key=lambda row: row["missing_pct"], reverse=True)

    zero_alerts = [row for row in (parse_zero_alert(a) for a in alert_rows) if row]
    zero_alerts.sort(key=lambda row: row["zero_pct"], reverse=True)

    imbalance_alerts = [row for row in (parse_imbalance_alert(a) for a in alert_rows) if row]
    imbalance_alerts.sort(key=lambda row: row["dominant_pct"], reverse=True)

    profile_summary = {
        "number_of_variables": parse_number(stats_raw.get("number_of_variables", "")),
        "number_of_observations": parse_number(stats_raw.get("number_of_observations", "")),
        "missing_cells": parse_number(stats_raw.get("missing_cells", "")),
        "missing_cells_pct": parse_number(stats_raw.get("missing_cells_pct", "").replace("%", "")),
        "total_memory_size_text": stats_raw.get("total_size_in_memory"),
        "total_memory_size_bytes": parse_size_to_bytes(stats_raw.get("total_size_in_memory", "")),
        "average_record_size_text": stats_raw.get("average_record_size_in_memory"),
        "average_record_size_bytes": parse_size_to_bytes(
            stats_raw.get("average_record_size_in_memory", "")
        ),
    }
    variable_types = {
        "numeric": parse_number(var_types_raw.get("numeric", "")),
        "categorical": parse_number(var_types_raw.get("categorical", "")),
        "boolean": parse_number(var_types_raw.get("boolean", "")),
    }

    return {
        "meta": {
            "source_file": path.name,
            "report_generated_at": report_date,
        },
        "dataset_statistics": profile_summary,
        "variable_types": variable_types,
        "alert_count": alert_count,
        "alert_type_counts": alert_type_counts,
        "top_missing_alerts": missing_alerts[:15],
        "top_zero_alerts": zero_alerts[:15],
        "top_imbalance_alerts": imbalance_alerts[:15],
        "alerts": alert_rows,
    }


def build_metrics(
    nb: dict[str, Any], chart_files: dict[str, str], profile_report: dict[str, Any] | None
) -> dict[str, Any]:
    shape_text = get_stream_text(get_cell(nb, 7))
    feature_count_text = get_stream_text(get_cell(nb, 11))
    target_text = get_stream_text(get_cell(nb, 13))
    iqr_bounds_text = get_stream_text(get_cell(nb, 21))
    iqr_rows_text = get_stream_text(get_cell(nb, 23))

    top_corr_text = get_first_text_plain(get_cell(nb, 33))
    top_driver_text = get_first_text_plain(get_cell(nb, 35))
    top_neigh_text = get_first_text_plain(get_cell(nb, 46))
    top_neigh_single_text = get_first_text_plain(get_cell(nb, 47))
    missing_text = get_first_text_plain(get_cell(nb, 27))

    total_rows, total_columns = parse_shape(shape_text)
    numeric_features, categorical_features = parse_feature_counts(feature_count_text)
    target_stats = parse_target_stats(target_text)
    iqr_bounds = parse_iqr_bounds(iqr_bounds_text)
    iqr_rows = parse_iqr_row_counts(iqr_rows_text)
    top_correlations = parse_correlation_table(top_corr_text)
    top_drivers = parse_driver_list(top_driver_text)
    top_neighborhoods = parse_neighborhood_table(top_neigh_text)
    top_neighborhood_single = parse_neighborhood_table(top_neigh_single_text)
    missing_features = parse_missing_table(
        missing_text, iqr_rows.get("rows_after_iqr")  # type: ignore[arg-type]
    )

    top_driver_details: list[dict[str, float | str | None]] = []
    corr_by_feature = {row["feature"]: row["correlation"] for row in top_correlations}
    for feature in top_drivers:
        top_driver_details.append(
            {
                "feature": feature,
                "correlation": corr_by_feature.get(feature),
            }
        )

    top_neighborhood = top_neighborhood_single[0] if top_neighborhood_single else None

    summary = {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        **target_stats,
        **iqr_bounds,
        **iqr_rows,
    }

    metrics = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_notebook": str(NOTEBOOK_PATH.name),
            "source_note": "Values and chart outputs extracted from executed notebook cells.",
            "source_profile": (
                profile_report["meta"]["source_file"] if profile_report else None
            ),
        },
        "summary": summary,
        "top_correlations": top_correlations,
        "top_drivers": top_driver_details,
        "top_neighborhoods": top_neighborhoods,
        "top_neighborhood": top_neighborhood,
        "top_missing_features": missing_features,
        "profile_overview": profile_report,
        "managerial_summary": {
            "top_drivers_plain_english": [
                "Quality, living area, and utility space are the strongest value levers.",
                "Log transform stabilizes SalePrice distribution for modeling.",
                "Neighborhood premium effects are strong and interpretable.",
            ],
            "risks": [
                "High missing-rate fields often indicate absence of amenity, not random missingness.",
                "Rare category segments can overfit if not regularized.",
                "Untrimmed outliers can skew linear relationships.",
            ],
            "next_steps": [
                "Engineer total space and age-based features.",
                "Encode none/absence categories explicitly for categorical fields.",
                "Benchmark regularized linear models, then compare with tree ensembles.",
            ],
        },
        "chart_files": chart_files,
    }
    return metrics


def write_metrics(metrics: dict[str, Any]) -> None:
    json_path = DATA_DIR / "metrics.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    js_path = JS_DIR / "metrics.js"
    with js_path.open("w", encoding="utf-8") as file:
        file.write("window.dashboardMetrics = ")
        file.write(json.dumps(metrics, indent=2))
        file.write(";\n")


def main() -> None:
    if not NOTEBOOK_PATH.exists():
        raise FileNotFoundError(f"Notebook not found: {NOTEBOOK_PATH}")

    ensure_dirs()
    notebook = load_notebook(NOTEBOOK_PATH)
    chart_files = export_charts(notebook)

    profile_report = None
    profile_path = find_profile_path()
    if profile_path:
        profile_report = parse_profile_report(profile_path)

    metrics = build_metrics(notebook, chart_files, profile_report)
    write_metrics(metrics)

    print("Dashboard assets generated from notebook/profile outputs:")
    print(f"- Charts: {CHARTS_DIR}")
    print(f"- Data:   {DATA_DIR / 'metrics.json'}")
    print(f"- JS:     {JS_DIR / 'metrics.js'}")
    if profile_path:
        print(f"- Profile parsed: {profile_path.name}")
    else:
        print("- Profile parsed: not found")


if __name__ == "__main__":
    main()
