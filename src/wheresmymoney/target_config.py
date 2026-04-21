from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class TargetSheetConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TargetSheetConfig:
    spreadsheet_id: str
    categories_sheet_name: str
    allowed_bank_tabs: tuple[str, ...]
    protected_analysis_tabs: tuple[str, ...]
    transaction_start_row: int
    bank_tab_columns: tuple[str, ...]
    deterministic_rules_path: str | None = None

    @classmethod
    def from_file(cls, file_path: str | Path) -> "TargetSheetConfig":
        config_path = Path(file_path)
        try:
            raw_config = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TargetSheetConfigError(
                f"Config file not found: {config_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise TargetSheetConfigError(
                f"Invalid JSON in config file: {config_path}"
            ) from exc

        return cls.from_dict(raw_config)

    @classmethod
    def from_dict(cls, raw_config: dict) -> "TargetSheetConfig":
        required_keys = (
            "spreadsheet_id",
            "categories_sheet_name",
            "allowed_bank_tabs",
            "protected_analysis_tabs",
            "transaction_start_row",
            "bank_tab_columns",
        )
        missing_keys = [key for key in required_keys if key not in raw_config]
        if missing_keys:
            missing = ", ".join(missing_keys)
            raise TargetSheetConfigError(f"Missing config keys: {missing}")

        config = cls(
            spreadsheet_id=_require_non_empty_string(
                raw_config["spreadsheet_id"], "spreadsheet_id"
            ),
            categories_sheet_name=_require_non_empty_string(
                raw_config["categories_sheet_name"], "categories_sheet_name"
            ),
            allowed_bank_tabs=_require_string_list(
                raw_config["allowed_bank_tabs"], "allowed_bank_tabs"
            ),
            protected_analysis_tabs=_require_string_list(
                raw_config["protected_analysis_tabs"], "protected_analysis_tabs"
            ),
            transaction_start_row=_require_positive_int(
                raw_config["transaction_start_row"], "transaction_start_row"
            ),
            bank_tab_columns=_require_string_list(
                raw_config["bank_tab_columns"], "bank_tab_columns"
            ),
            deterministic_rules_path=_optional_non_empty_string(
                raw_config.get("deterministic_rules_path"),
                "deterministic_rules_path",
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        overlap = set(self.allowed_bank_tabs) & set(self.protected_analysis_tabs)
        if overlap:
            duplicated_tabs = ", ".join(sorted(overlap))
            raise TargetSheetConfigError(
                "Tabs cannot be both allowed and protected: "
                f"{duplicated_tabs}"
            )

        if self.categories_sheet_name in self.allowed_bank_tabs:
            raise TargetSheetConfigError(
                "categories_sheet_name cannot be one of the bank tabs"
            )

        if len(set(self.allowed_bank_tabs)) != len(self.allowed_bank_tabs):
            raise TargetSheetConfigError("allowed_bank_tabs contains duplicates")

        if len(set(self.protected_analysis_tabs)) != len(
            self.protected_analysis_tabs
        ):
            raise TargetSheetConfigError(
                "protected_analysis_tabs contains duplicates"
            )

        if len(set(self.bank_tab_columns)) != len(self.bank_tab_columns):
            raise TargetSheetConfigError("bank_tab_columns contains duplicates")

    def ensure_writable_tab(self, tab_name: str) -> None:
        if tab_name in self.protected_analysis_tabs:
            raise TargetSheetConfigError(
                f"Tab '{tab_name}' is protected and cannot be used as a target"
            )
        if tab_name not in self.allowed_bank_tabs:
            raise TargetSheetConfigError(
                f"Tab '{tab_name}' is not listed among allowed bank tabs"
            )


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetSheetConfigError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_non_empty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name)


def _require_string_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TargetSheetConfigError(
            f"{field_name} must be a non-empty list of strings"
        )

    normalized = []
    for item in value:
        normalized.append(_require_non_empty_string(item, field_name))
    return tuple(normalized)


def _require_positive_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise TargetSheetConfigError(f"{field_name} must be a positive integer")
    return value