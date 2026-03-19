"""
Table metadata loader (standalone, matching service implementation).
"""

import bisect
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from scripts.helpers import run_in_threadpool


class TableMetadataLoader:
    """Loads table metadata from JSON files."""

    # Size categories and impact multipliers matching service
    SIZE_CATEGORIES = {
        "tiny": {"max": 1000, "multiplier": 0.1, "severity": "10% of baseline (minimal impact)"},
        "small": {"max": 10000, "multiplier": 0.5, "severity": "50% of baseline (minor impact)"},
        "medium": {"max": 100000, "multiplier": 1.0, "severity": "baseline severity"},
        "large": {"max": 1000000, "multiplier": 1.5, "severity": "150% of baseline (high impact)"},
        "very_large": {"max": float("inf"), "multiplier": 2.5, "severity": "250% of baseline (critical concern)"},
    }

    @staticmethod
    def _load_single_json(json_file: Path) -> Optional[tuple[str, Dict[str, Any]]]:
        """Load a single JSON file and return (normalized_name, metadata) tuple."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            table_name = data.get("table_name", "")
            table_id = data.get("table_id", "")
            row_count = data.get("rows", 0)

            if not table_name:
                return None

            # Categorize by size
            size_category, category_info = TableMetadataLoader._categorize_size(row_count)

            # Normalize name for case-insensitive lookup
            normalized_name = table_name.lower().strip()

            metadata = {
                "name": table_name,
                "id": table_id,
                "rows": row_count,
                "rowCount": row_count,  # Alias for compatibility
                "sizeCategory": size_category,
                "impactMultiplier": category_info["multiplier"],
                "friendlySize": TableMetadataLoader._get_friendly_size(row_count),
                "severityAdjustment": category_info["severity"],
            }

            return (normalized_name, metadata)

        except Exception:
            # Skip files that can't be parsed
            return None

    @lru_cache(maxsize=None)
    @staticmethod
    def load_metadata(dir: str | None = None) -> Dict[str, Dict[str, Any]]:
        """
        Load all table metadata from JSON files in parallel.

        Returns:
            Dict mapping normalized table names to metadata dicts with:
            - name: original table name
            - id: table ID
            - rows: row count
            - sizeCategory: size category (tiny/small/medium/large/very_large)
            - impactMultiplier: multiplier for bottleneck scores
            - friendlySize: human-readable size description
            - severityAdjustment: severity adjustment description
        """
        if dir:
            data_dir = Path(dir)
        elif env_dir := os.environ.get("TABLES_DIR"):
            data_dir = Path(env_dir)
        else:
            path = Path(__file__).resolve().parent
            data_dir = None
            for _ in range(8):
                candidate = path / "data" / "tables"
                if candidate.exists():
                    data_dir = candidate
                    break
                path = path.parent
            if data_dir is None:
                data_dir = Path(__file__).parent.parent.parent.parent / "data" / "tables"

        if not data_dir.exists():
            return {}

        # Get all JSON files
        json_files = list(data_dir.glob("*.json"))

        if not json_files:
            return {}

        # Load all files in parallel using threadpool
        results = run_in_threadpool(TableMetadataLoader._load_single_json, ((f,) for f in json_files))

        # Merge results into metadata dict
        metadata = {}
        for result in results:
            if result:
                normalized_name, table_meta = result
                metadata[normalized_name] = table_meta

        return metadata

    @staticmethod
    def _categorize_size(row_count: int) -> tuple[str, Dict[str, Any]]:
        """Categorize table size based on row count."""
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
