from __future__ import annotations

import sys
from dataclasses import dataclass

import gspread

from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError
from wheresmymoney.target_config import TargetSheetConfig


class CategoryError(ValueError):
    pass


@dataclass(frozen=True)
class CategoryCatalog:
    categories: tuple[str, ...]

    def ensure_valid(self, category: str) -> str:
        normalized = _normalize_cell(category)
        if normalized not in self.categories:
            raise CategoryError(f"Unknown category: {category}")
        return normalized


def load_categories(
    runtime_config: RuntimeConfig,
    target_config: TargetSheetConfig,
) -> CategoryCatalog:
    if runtime_config.google_service_account_json is None:
        raise RuntimeConfigError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is required to load categories"
        )

    client = gspread.service_account(
        filename=str(runtime_config.google_service_account_json)
    )
    worksheet = client.open_by_key(target_config.spreadsheet_id).worksheet(
        target_config.categories_sheet_name
    )
    values = worksheet.col_values(1)
    return build_category_catalog(values, header_name=target_config.categories_sheet_name)


def build_category_catalog(
    first_column_values: list[str],
    *,
    header_name: str,
) -> CategoryCatalog:
    categories: list[str] = []
    seen: set[str] = set()
    normalized_header = _normalize_cell(header_name)

    for raw_value in first_column_values:
        normalized = _normalize_cell(raw_value)
        if not normalized:
            continue
        if normalized.casefold() == normalized_header.casefold():
            continue
        if normalized in seen:
            raise CategoryError(f"Duplicate category found: {normalized}")
        seen.add(normalized)
        categories.append(normalized)

    if not categories:
        raise CategoryError("No categories found in the category sheet")

    return CategoryCatalog(categories=tuple(categories))


def _normalize_cell(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def cli_main() -> int:
    from wheresmymoney.runtime_config import RuntimeConfig
    from wheresmymoney.target_config import TargetSheetConfig

    try:
        runtime_config = RuntimeConfig.from_env()
        target_config = TargetSheetConfig.from_file(
            runtime_config.target_sheet_config_path
        )
        catalog = load_categories(runtime_config, target_config)
    except (RuntimeConfigError, CategoryError, FileNotFoundError, gspread.GSpreadException) as exc:
        print(f"Category loading failed: {exc}", file=sys.stderr)
        return 1

    for category in catalog.categories:
        print(category)
    return 0