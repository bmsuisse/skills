import bisect
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from helpers import run_in_processpool


class TableMetadataLoader:
    SIZE_CATEGORIES = {
        "tiny": {"max": 1000, "multiplier": 0.1, "severity": "10% of baseline (minimal impact)"},
        "small": {"max": 10000, "multiplier": 0.5, "severity": "50% of baseline (minor impact)"},
        "medium": {"max": 100000, "multiplier": 1.0, "severity": "baseline severity"},
        "large": {"max": 1000000, "multiplier": 1.5, "severity": "150% of baseline (high impact)"},
        "very_large": {"max": float("inf"), "multiplier": 2.5, "severity": "250% of baseline (critical concern)"},
    }

    # Column-width categories used by SETLOADFIELDS severity scoring.
    # A wider table means more bytes wasted on every SELECT * when SETLOADFIELDS is missing.
    COLUMN_WIDTH_CATEGORIES: Dict[str, Dict[str, Any]] = {
        "narrow":    {"max": 10,            "multiplier": 0.5,  "label": "narrow (≤10 fields)"},
        "medium":    {"max": 30,            "multiplier": 1.0,  "label": "medium (11-30 fields)"},
        "wide":      {"max": 60,            "multiplier": 1.5,  "label": "wide (31-60 fields)"},
        "very_wide": {"max": float("inf"), "multiplier": 2.0,  "label": "very wide (>60 fields)"},
    }

    @staticmethod
    def _load_single_json(json_file: Path) -> Optional[tuple[str, Dict[str, Any]]]:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            table_name = data.get("table_name", "")
            table_id = data.get("table_id", "")
            row_count = data.get("rows", 0)

            if not table_name:
                return None

            size_category, category_info = TableMetadataLoader._categorize_size(row_count)
            normalized_name = table_name.lower().strip()

            # Column-count fields are optional — if not present in JSON, defaults are safe neutrals
            field_count: int = int(data.get("field_count", 0))
            has_flow_fields: bool = bool(data.get("has_flow_fields", False))
            col_category, col_multiplier = TableMetadataLoader._categorize_column_width(field_count)

            metadata = {
                "name": table_name,
                "id": table_id,
                "rows": row_count,
                "rowCount": row_count,
                "sizeCategory": size_category,
                "impactMultiplier": category_info["multiplier"],
                "friendlySize": TableMetadataLoader._get_friendly_size(row_count),
                "severityAdjustment": category_info["severity"],
                # Column-width fields (used by SETLOADFIELDS analyzer)
                "fieldCount": field_count,
                "hasFlowFields": has_flow_fields,
                "columnWidthCategory": col_category,
                "columnWidthMultiplier": col_multiplier,
            }

            return (normalized_name, metadata)

        except Exception:
            return None

    @lru_cache(maxsize=None)
    @staticmethod
    def load_metadata(dir: str | None = None) -> Dict[str, Dict[str, Any]]:
        script_dir = Path(__file__).parent
        data_dir = Path(dir) if dir else script_dir.parent.parent.parent / "data" / "tables"

        if not data_dir.exists():
            return {}

        json_files = list(data_dir.glob("*.json"))

        if not json_files:
            return {}

        results = run_in_processpool(TableMetadataLoader._load_single_json, ((f,) for f in json_files))

        metadata = {}
        for result in results:
            if result:
                normalized_name, table_meta = result
                metadata[normalized_name] = table_meta

        return metadata

    @staticmethod
    def _categorize_size(row_count: int) -> tuple[str, Dict[str, Any]]:
        for category, info in TableMetadataLoader.SIZE_CATEGORIES.items():
            if row_count < info["max"]:
                return category, info

        return "very_large", TableMetadataLoader.SIZE_CATEGORIES["very_large"]

    @staticmethod
    def _get_friendly_size(row_count: int) -> str:
        thresholds = [0, 1000, 10000, 100000, 1000000]
        labels = ["empty", "tiny", "small", "medium", "large", "very large"]
        label = labels[bisect.bisect_right(thresholds, row_count) - 1]

        return f"{row_count:,} rows ({label})" if row_count else "empty"

    @staticmethod
    def _categorize_column_width(field_count: int) -> tuple[str, float]:
        """Return (category_name, column_width_multiplier) based on how many fields the table has.

        When field_count is unknown (0 / not in JSON), we return a neutral multiplier of 1.0
        so it doesn't artificially inflate or deflate SETLOADFIELDS urgency scores.
        """
        if field_count <= 0:
            return "unknown", 1.0
        for category, info in TableMetadataLoader.COLUMN_WIDTH_CATEGORIES.items():
            if field_count < info["max"]:
                return category, info["multiplier"]
        return "very_wide", TableMetadataLoader.COLUMN_WIDTH_CATEGORIES["very_wide"]["multiplier"]
