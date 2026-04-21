from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class TransactionError(ValueError):
    pass


@dataclass(frozen=True)
class Transaction:
    source_bank: str
    transaction_date: date
    value_date: date
    amount: Decimal
    currency: str
    original_description: str
    cleaned_description: str | None = None
    assigned_category: str | None = None
    raw_row_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_bank", _require_non_empty_string(self.source_bank, "source_bank")
        )
        object.__setattr__(
            self,
            "transaction_date",
            normalize_date(self.transaction_date, "transaction_date"),
        )
        object.__setattr__(
            self,
            "value_date",
            normalize_date(self.value_date, "value_date"),
        )
        object.__setattr__(self, "amount", normalize_amount(self.amount))
        object.__setattr__(self, "currency", normalize_currency(self.currency))
        object.__setattr__(
            self,
            "original_description",
            _require_non_empty_preserved_string(
                self.original_description,
                "original_description",
            ),
        )
        object.__setattr__(
            self,
            "cleaned_description",
            _normalize_optional_string(self.cleaned_description),
        )
        object.__setattr__(
            self,
            "assigned_category",
            _normalize_optional_string(self.assigned_category),
        )
        object.__setattr__(self, "raw_row_id", _normalize_optional_string(self.raw_row_id))

    @property
    def effective_description(self) -> str:
        return self.cleaned_description or self.original_description

    @property
    def sheet_description(self) -> str:
        return self.original_description

    def to_sheet_row(self, column_order: list[str] | tuple[str, ...]) -> list[str]:
        if any(column.strip().lower() == "mese" for column in column_order):
            raise TransactionError("The 'Mese' column must not be written by the app")

        mapping = {
            "Data Valuta": self.value_date.strftime("%d/%m/%Y"),
            "Importo": format(self.amount, "f"),
            "Divisa": self.currency,
            "Cat": self.assigned_category or "",
            "Descrizione": self.sheet_description,
        }

        row: list[str] = []
        for column in column_order:
            if column not in mapping:
                raise TransactionError(
                    f"Unsupported sheet column for transaction export: {column}"
                )
            row.append(mapping[column])
        return row


def normalize_date(value: date | datetime | str, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise TransactionError(f"{field_name} must be a non-empty date value")

    normalized = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    raise TransactionError(
        f"{field_name} must use dd/mm/yyyy or yyyy-mm-dd format"
    )


def normalize_amount(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))

    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    if not isinstance(value, str) or not value.strip():
        raise TransactionError("amount must be a non-empty numeric value")

    normalized = value.strip().replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "")
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise TransactionError(f"Invalid amount value: {value}") from exc


def normalize_currency(value: str) -> str:
    currency = _require_non_empty_string(value, "currency").upper()
    if len(currency) != 3:
        raise TransactionError("currency must be a 3-letter ISO code")
    return currency


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransactionError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_non_empty_preserved_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransactionError(f"{field_name} must be a non-empty string")
    return value


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TransactionError("Optional textual fields must be strings")
    normalized = value.strip()
    return normalized or None