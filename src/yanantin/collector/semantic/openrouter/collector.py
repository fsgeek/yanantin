"""OpenRouter activity collector — reads CSV exports into typed models.

Reads OpenRouter's activity CSV format. Each row becomes an
OpenRouterActivityRow. The collector handles CSV parsing, type
coercion, and the messy reality of CSV data (empty strings for
missing values, inconsistent quoting, etc.).

Supports incremental collection via the ``since`` parameter —
only rows newer than the given timestamp are returned.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.semantic.openrouter.models import (
    OpenRouterActivity,
    OpenRouterActivityRow,
)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _parse_float(value: str) -> float:
    value = value.strip()
    if not value:
        return 0.0
    return float(value)


def _parse_int(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    return int(float(value))


def _parse_datetime(value: str) -> datetime:
    """Parse OpenRouter's timestamp format, ensuring UTC."""
    value = value.strip()
    dt = datetime.fromisoformat(value) if "T" in value else datetime.strptime(
        value, "%Y-%m-%d %H:%M:%S.%f"
    )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_model(row: dict[str, str]) -> OpenRouterActivityRow:
    """Convert a CSV row dict to a typed model.

    Handles the CSV's quirks: empty strings for missing values,
    all values as strings, inconsistent boolean representations.
    """
    return OpenRouterActivityRow(
        generation_id=row.get("generation_id", ""),
        created_at=_parse_datetime(row["created_at"]),
        cost_total=_parse_float(row.get("cost_total", "")),
        cost_web_search=_parse_float(row.get("cost_web_search", "")),
        cost_cache=_parse_float(row.get("cost_cache", "")),
        cost_file_processing=_parse_float(row.get("cost_file_processing", "")),
        byok_usage_inference=_parse_float(row.get("byok_usage_inference", "")),
        tokens_prompt=_parse_int(row.get("tokens_prompt", "")),
        tokens_completion=_parse_int(row.get("tokens_completion", "")),
        tokens_reasoning=_parse_int(row.get("tokens_reasoning", "")),
        tokens_cached=_parse_int(row.get("tokens_cached", "")),
        model_permaslug=row.get("model_permaslug", ""),
        provider_name=row.get("provider_name", ""),
        variant=row.get("variant", ""),
        cancelled=_parse_bool(row.get("cancelled", "")),
        streamed=_parse_bool(row.get("streamed", "")),
        user=row.get("user", ""),
        finish_reason_raw=row.get("finish_reason_raw", ""),
        finish_reason_normalized=row.get("finish_reason_normalized", ""),
        generation_time_ms=_parse_int(row.get("generation_time_ms", "")),
        time_to_first_token_ms=_parse_int(row.get("time_to_first_token_ms", "")),
        app_name=row.get("app_name", ""),
        api_key_name=row.get("api_key_name", ""),
    )


class OpenRouterActivityCollector(CollectorBase[OpenRouterActivity]):
    """Reads OpenRouter activity CSV exports.

    Provider ID is deterministic per source file path — the same CSV
    always produces the same provider UUID.
    """

    def __init__(self, csv_path: str | Path) -> None:
        self._csv_path = Path(csv_path)
        self._provider_id = uuid5(
            NAMESPACE_DNS,
            f"yanantin.collector.openrouter.{self._csv_path.name}",
        )

    def collect(self, since: datetime | None = None) -> OpenRouterActivity:
        """Read the CSV and return typed rows.

        If ``since`` is provided, only rows with created_at > since
        are included. This supports incremental ingestion.
        """
        rows: list[OpenRouterActivityRow] = []

        with open(self._csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                try:
                    row = _row_to_model(raw_row)
                except (ValueError, KeyError) as e:
                    # Log before you parse — the raw data survives
                    import logging
                    logging.getLogger(__name__).warning(
                        "Skipping malformed row: %s — error: %s",
                        raw_row.get("generation_id", "unknown"),
                        e,
                    )
                    continue

                if since is not None and row.created_at <= since:
                    continue

                rows.append(row)

        return OpenRouterActivity(
            rows=tuple(rows),
            source_file=str(self._csv_path),
        )

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return f"OpenRouter activity collector — reads {self._csv_path.name}"
