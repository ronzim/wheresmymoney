from __future__ import annotations

from typing import Protocol

import click

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.models import Transaction
from wheresmymoney.review_cli import (
    ReviewStyler,
    _format_category_choice_grid,
    review_transactions_interactively,
)


class PromptUITestDouble(Protocol):
    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        ...

    def confirm(self, message: str, default: bool = False) -> bool:
        ...


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
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo"],
        header_name="Categorie",
    )
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
    assert any("Riepilogo finale" in line for line in outputs)
    assert any("#  Data       Importo" in line for line in outputs)


def test_review_cli_changes_category_by_index() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo", "Viaggi"],
        header_name="Categorie",
    )
    outputs: list[str] = []
    answers = iter(["1", "y"])

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Mutuo"


def test_review_cli_changes_category_by_unique_prefix() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo", "Viaggi"],
        header_name="Categorie",
    )
    answers = iter(["mu", "y"])

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=lambda _message: None,
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Mutuo"


def test_review_cli_prints_full_cleaned_description_and_category_after_it() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo"],
        header_name="Categorie",
    )
    outputs: list[str] = []
    cleaned_description = (
        "Supermercato di quartiere con dettaglio completo senza alcun taglio "
        "della descrizione ripulita"
    )
    answers = iter(["", "y"])

    review_transactions_interactively(
        [_transaction(cleaned_description=cleaned_description)],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    cleaned_index = next(
        index for index, line in enumerate(outputs)
        if "Descrizione pulita" in line
    )
    category_index = next(
        index for index, line in enumerate(outputs)
        if "Categoria proposta" in line
    )

    assert cleaned_description in outputs[cleaned_index]
    assert cleaned_index < category_index


def test_review_cli_lists_categories_in_alphabetical_grid() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo", "Animali", "Viaggi"],
        header_name="Categorie",
    )
    outputs: list[str] = []
    answers = iter(["?", "", "y"])

    review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert any(
        "1. Animali" in line and "2. Mutuo" in line for line in outputs
    )
    assert any(
        "3. Spesa" in line and "4. Viaggi" in line for line in outputs
    )


def test_format_category_choice_grid_alternates_colors() -> None:
    lines = _format_category_choice_grid(
        ["Animali", "Mutuo", "Spesa"],
        styler=ReviewStyler(enabled=True),
    )

    assert any(click.style("1. Animali", fg="bright_cyan") in line for line in lines)
    assert any(click.style("2. Mutuo", fg="bright_yellow") in line for line in lines)
    assert any(click.style("3. Spesa", fg="bright_cyan") in line for line in lines)


def test_review_cli_reprompts_on_invalid_choice_and_can_cancel() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo"],
        header_name="Categorie",
    )
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
    assert any("Indice non valido" in line for line in outputs)
    assert any("Operazione annullata" in line for line in outputs)


def test_review_cli_can_reopen_transaction_from_final_summary() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo", "Viaggi"],
        header_name="Categorie",
    )
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
    assert any("Riepilogo finale" in line for line in outputs)


def test_review_cli_compacts_long_descriptions_in_summary() -> None:
    catalog = build_category_catalog(
        ["Categorie", "Spesa", "Mutuo"],
        header_name="Categorie",
    )
    outputs: list[str] = []
    long_description = (
        "addebito ricorrente con descrizione molto lunga per verificare "
        "che il riepilogo "
        "resti leggibile anche quando il testo supera la larghezza prevista"
    )
    answers = iter(["", "y"])

    review_transactions_interactively(
        [_transaction(original_description=long_description)],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
    )

    assert any(
        "addebito ricorrente con descrizione mol..." in line
        for line in outputs
    )


def test_review_cli_supports_many_categories_with_numeric_grid() -> None:
    categories = ["Categorie"] + [
        f"Categoria {index}" for index in range(1, 40)
    ]
    catalog = build_category_catalog(categories, header_name="Categorie")
    outputs: list[str] = []
    observed_choice_lengths: list[int] = []
    answers = iter(["33"])

    class PromptUIDouble:
        def autocomplete(
            self,
            _message: str,
            _choices: list[str],
            default: str = "",
        ) -> str:
            return "Categoria 39"

        def select(self, _message: str, choices: list[tuple[str, str]]) -> str:
            observed_choice_lengths.append(len(choices))
            return "__confirm__"

        def confirm(self, _message: str, default: bool = False) -> bool:
            return default

    result = review_transactions_interactively(
        [_transaction()],
        catalog,
        input_func=lambda _prompt: next(answers),
        output_func=outputs.append,
        prompt_ui=PromptUIDouble(),
    )

    assert result.confirmed is True
    assert result.reviewed_transactions[0].assigned_category == "Categoria 39"
    assert observed_choice_lengths == [3]
