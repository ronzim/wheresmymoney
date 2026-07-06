from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from wheresmymoney.models import Transaction


class ImportCheckpointError(ValueError):
    pass


@dataclass(frozen=True)
class ImportCheckpoint:
    file_path: str
    source_bank: str
    parser_name: str
    rule_classified_count: int
    llm_classified_count: int
    reviewed_count: int
    transactions: tuple[Transaction, ...]


def load_import_checkpoint(
    checkpoint_dir: Path,
    file_path: str | Path,
    source_bank: str,
) -> ImportCheckpoint | None:
    checkpoint_path = build_checkpoint_path(checkpoint_dir, file_path, source_bank)
    if not checkpoint_path.exists():
        return None

    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImportCheckpointError(
            f"Invalid JSON in checkpoint file: {checkpoint_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise ImportCheckpointError("Checkpoint payload must be a JSON object")

    transactions_payload = payload.get("transactions")
    if not isinstance(transactions_payload, list):
        raise ImportCheckpointError("Checkpoint transactions must be a JSON list")

    try:
        transactions = tuple(
            _transaction_from_payload(item) for item in transactions_payload
        )
        reviewed_count = int(payload["reviewed_count"])
        rule_classified_count = int(payload["rule_classified_count"])
        llm_classified_count = int(payload["llm_classified_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ImportCheckpointError(
            f"Checkpoint file is missing required fields: {checkpoint_path}"
        ) from exc

    if reviewed_count < 0 or reviewed_count > len(transactions):
        raise ImportCheckpointError("Checkpoint reviewed_count is out of bounds")

    return ImportCheckpoint(
        file_path=str(payload.get("file_path", "")),
        source_bank=str(payload.get("source_bank", "")),
        parser_name=str(payload.get("parser_name", "")),
        rule_classified_count=rule_classified_count,
        llm_classified_count=llm_classified_count,
        reviewed_count=reviewed_count,
        transactions=transactions,
    )


def save_import_checkpoint(
    checkpoint_dir: Path,
    checkpoint: ImportCheckpoint,
) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = build_checkpoint_path(
        checkpoint_dir,
        checkpoint.file_path,
        checkpoint.source_bank,
    )
    payload = {
        "file_path": checkpoint.file_path,
        "source_bank": checkpoint.source_bank,
        "parser_name": checkpoint.parser_name,
        "rule_classified_count": checkpoint.rule_classified_count,
        "llm_classified_count": checkpoint.llm_classified_count,
        "reviewed_count": checkpoint.reviewed_count,
        "transactions": [
            _transaction_to_payload(transaction)
            for transaction in checkpoint.transactions
        ],
    }
    checkpoint_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return checkpoint_path


def delete_import_checkpoint(
    checkpoint_dir: Path,
    file_path: str | Path,
    source_bank: str,
) -> None:
    checkpoint_path = build_checkpoint_path(checkpoint_dir, file_path, source_bank)
    if checkpoint_path.exists():
        checkpoint_path.unlink()


def build_checkpoint_path(
    checkpoint_dir: Path,
    file_path: str | Path,
    source_bank: str,
) -> Path:
    normalized_file_path = str(Path(file_path).resolve())
    key = hashlib.sha256(
        f"{source_bank}\n{normalized_file_path}".encode("utf-8")
    ).hexdigest()[:16]
    return checkpoint_dir / f"{source_bank}-{key}.json"


def _transaction_to_payload(transaction: Transaction) -> dict[str, str | None]:
    return {
        "source_bank": transaction.source_bank,
        "transaction_date": transaction.transaction_date.isoformat(),
        "value_date": transaction.value_date.isoformat(),
        "amount": format(transaction.amount, "f"),
        "currency": transaction.currency,
        "original_description": transaction.original_description,
        "cleaned_description": transaction.cleaned_description,
        "assigned_category": transaction.assigned_category,
        "raw_row_id": transaction.raw_row_id,
    }


def _transaction_from_payload(payload: object) -> Transaction:
    if not isinstance(payload, dict):
        raise ImportCheckpointError("Each checkpoint transaction must be an object")

    try:
        return Transaction(
            source_bank=str(payload["source_bank"]),
            transaction_date=str(payload["transaction_date"]),
            value_date=str(payload["value_date"]),
            amount=str(payload["amount"]),
            currency=str(payload["currency"]),
            original_description=str(payload["original_description"]),
            cleaned_description=payload.get("cleaned_description"),
            assigned_category=payload.get("assigned_category"),
            raw_row_id=payload.get("raw_row_id"),
        )
    except KeyError as exc:
        raise ImportCheckpointError(
            "Checkpoint transaction is missing required fields"
        ) from exc