from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from wheresmymoney.categories import CategoryCatalog
from wheresmymoney.models import Transaction


class ReviewCLIError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewSessionResult:
    reviewed_transactions: tuple[Transaction, ...]
    confirmed: bool


def review_transactions_interactively(
    transactions: list[Transaction] | tuple[Transaction, ...],
    category_catalog: CategoryCatalog,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> ReviewSessionResult:
    reviewed_transactions: list[Transaction] = []

    for index, transaction in enumerate(transactions, start=1):
        reviewed_transactions.append(
            _review_single_transaction(
                index,
                len(transactions),
                transaction,
                category_catalog,
                input_func=input_func,
                output_func=output_func,
            )
        )

    finalized_transactions, confirmed = _finalize_review(
        reviewed_transactions,
        category_catalog,
        input_func=input_func,
        output_func=output_func,
    )
    return ReviewSessionResult(
        reviewed_transactions=tuple(finalized_transactions),
        confirmed=confirmed,
    )


def _review_single_transaction(
    index: int,
    total: int,
    transaction: Transaction,
    category_catalog: CategoryCatalog,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> Transaction:
    output_func(f"Transazione {index}/{total}")
    output_func(f"Data movimento: {transaction.transaction_date.strftime('%d/%m/%Y')}")
    output_func(f"Data valuta: {transaction.value_date.strftime('%d/%m/%Y')}")
    output_func(f"Importo: {format(transaction.amount, 'f')} {transaction.currency}")
    output_func(f"Descrizione originale: {transaction.original_description}")
    output_func(f"Descrizione pulita: {transaction.cleaned_description or ''}")
    output_func(f"Categoria proposta: {transaction.assigned_category or FALLBACK_REVIEW_CATEGORY}")

    while True:
        output_func("Categorie disponibili:")
        for category_index, category in enumerate(category_catalog.categories, start=1):
            output_func(f"  {category_index}. {category}")
        answer = input_func(
            "Invio = tieni la categoria proposta, numero = cambia categoria: "
        ).strip()

        if not answer:
            return transaction

        if answer.isdigit():
            selected_index = int(answer)
            if 1 <= selected_index <= len(category_catalog.categories):
                selected_category = category_catalog.categories[selected_index - 1]
                return replace(transaction, assigned_category=selected_category)

        output_func("Scelta non valida. Inserisci Invio oppure un numero presente in lista.")


def _confirm_review(
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> bool:
    while True:
        answer = input_func("Confermare il salvataggio su Google Sheets? [y/N]: ").strip().lower()
        if answer in {"y", "yes", "s", "si"}:
            output_func("Conferma registrata.")
            return True
        if answer in {"", "n", "no"}:
            output_func("Operazione annullata. Nessuna scrittura verra' eseguita.")
            return False
        output_func("Risposta non valida. Usa 'y' oppure 'n'.")


def _finalize_review(
    reviewed_transactions: list[Transaction],
    category_catalog: CategoryCatalog,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> tuple[list[Transaction], bool]:
    while True:
        _print_review_summary(reviewed_transactions, output_func=output_func)
        answer = input_func(
            "Conferma finale: 'y' per salvare, 'n' per annullare, numero per modificare una transazione: "
        ).strip().lower()

        if answer.isdigit():
            selected_index = int(answer)
            if 1 <= selected_index <= len(reviewed_transactions):
                reviewed_transactions[selected_index - 1] = _review_single_transaction(
                    selected_index,
                    len(reviewed_transactions),
                    reviewed_transactions[selected_index - 1],
                    category_catalog,
                    input_func=input_func,
                    output_func=output_func,
                )
                continue
            output_func("Indice non valido. Scegli un numero presente nel riepilogo.")
            continue

        if answer in {"l", "list"}:
            continue

        if answer in {"y", "yes", "s", "si"}:
            output_func("Conferma registrata.")
            return reviewed_transactions, True

        if answer in {"", "n", "no"}:
            output_func("Operazione annullata. Nessuna scrittura verra' eseguita.")
            return reviewed_transactions, False

        output_func("Risposta non valida. Usa 'y', 'n' oppure il numero di una transazione.")


def _print_review_summary(
    reviewed_transactions: list[Transaction],
    *,
    output_func: Callable[[str], None],
) -> None:
    output_func("Riepilogo finale:")
    for index, transaction in enumerate(reviewed_transactions, start=1):
        output_func(
            f"  {index}. {transaction.value_date.strftime('%d/%m/%Y')} | "
            f"{format(transaction.amount, 'f')} {transaction.currency} | "
            f"{transaction.assigned_category or FALLBACK_REVIEW_CATEGORY} | "
            f"{transaction.original_description}"
        )


FALLBACK_REVIEW_CATEGORY = "Da Verificare"