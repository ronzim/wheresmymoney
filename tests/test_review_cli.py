from __future__ import annotations

from pathlib import Path

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.models import Transaction
from wheresmymoney.review_cli import review_transactions_interactively


def _transaction(**overrides: str) -> Transaction:
    payload = {
        "source_bank": "Lisa",
        "transaction_date": "01/01/2026",
        "value_date": "01/01/2026",
        "amount": "-20,00",
        "currency": "EUR",
        "original_description": "spesa supermercato quartiere",
        "cleaned_description": "Supermercato",
        "assigned_category": "Spesa",
    }
    payload.update(overrides)
    return Transaction(**payload)


def test_review_cli_keeps_proposed_category_and_confirms() -> None:
    catalog = build_category_catalog(["Categorie", "Spesa", "Mutuo"], header_name="Categorie")
    prompts: list[str] = []
    outputs: list[str] = []
    answers = iter(["", "y"])

    def input_func(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=input_func,
        output_func=outputs.append,
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Spesa"
    assert any("Categoria proposta: Spesa" in line for line in outputs)
    assert any("Riepilogo finale:" in line for line in outputs)


def test_review_cli_changes_category_by_index() -> None:
    catalog = build_category_catalog(["Categorie", "Spesa", "Mutuo", "Viaggi"], header_name="Categorie")
    outputs: list[str] = []
    answers = iter(["2", "y"])

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Mutuo"


def test_review_cli_reprompts_on_invalid_choice_and_can_cancel() -> None:
    catalog = build_category_catalog(["Categorie", "Spesa", "Mutuo"], header_name="Categorie")
    outputs: list[str] = []
    answers = iter(["99", "", "n"])

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert result.confirmed is False
    assert result.reviewed_transactions[0].assigned_category == "Spesa"
    assert any("Scelta non valida" in line for line in outputs)
    assert any("Operazione annullata" in line for line in outputs)


def test_review_cli_can_reopen_transaction_from_final_summary() -> None:
    catalog = build_category_catalog(["Categorie", "Spesa", "Mutuo", "Viaggi"], header_name="Categorie")
    outputs: list[str] = []
    answers = iter(["", "1", "3", "y"])

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Viaggi"
    assert any("Riepilogo finale:" in line for line in outputs)