from __future__ import annotations

import sys
from shutil import get_terminal_size
from dataclasses import dataclass, replace
from typing import Callable, Protocol

import click

from wheresmymoney.categories import CategoryCatalog
from wheresmymoney.models import Transaction


class ReviewCLIError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewSessionResult:
    reviewed_transactions: tuple[Transaction, ...]
    confirmed: bool


@dataclass(frozen=True)
class ReviewStyler:
    enabled: bool = False

    def accent(self, text: str) -> str:
        return self._wrap(text, fg="cyan")

    def success(self, text: str) -> str:
        return self._wrap(text, fg="green")

    def danger(self, text: str) -> str:
        return self._wrap(text, fg="red")

    def muted(self, text: str) -> str:
        return self._wrap(text, fg="bright_black")

    def strong(self, text: str) -> str:
        return self._wrap(text, bold=True)

    def label(self, text: str) -> str:
        return self._wrap(text, fg="cyan", bold=True)

    def prompt(self, text: str) -> str:
        return self._wrap(text, fg="yellow", bold=True)

    def choice(self, text: str, index: int) -> str:
        return self._wrap(
            text,
            fg="bright_cyan" if index % 2 == 0 else "bright_yellow",
        )

    def _wrap(self, text: str, **style_kwargs: object) -> str:
        if not self.enabled:
            return text
        return click.style(text, **style_kwargs)


class PromptUI(Protocol):
    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        ...

    def confirm(self, message: str, default: bool = False) -> bool:
        ...

    def autocomplete(
        self,
        message: str,
        choices: list[str],
        default: str = "",
    ) -> str:
        ...


def review_transactions_interactively(
    transactions: list[Transaction] | tuple[Transaction, ...],
    category_catalog: CategoryCatalog,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    prompt_ui: PromptUI | None = None,
) -> ReviewSessionResult:
    styler = _build_review_styler(output_func=output_func)
    effective_prompt_ui = prompt_ui or _build_default_prompt_ui(
        input_func=input_func,
        output_func=output_func,
    )
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
                prompt_ui=effective_prompt_ui,
                styler=styler,
            )
        )

    finalized_transactions, confirmed = _finalize_review(
        reviewed_transactions,
        category_catalog,
        input_func=input_func,
        output_func=output_func,
        prompt_ui=effective_prompt_ui,
        styler=styler,
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
    prompt_ui: PromptUI | None,
    styler: ReviewStyler,
) -> Transaction:
    amount_label = _format_amount(transaction, styler=styler)
    proposed_category = (
        transaction.assigned_category or FALLBACK_REVIEW_CATEGORY
    )
    sorted_categories = _sorted_categories(category_catalog.categories)
    output_func("")
    output_func(
        styler.strong(
            "["
            f"{index}/{total}"
            "] "
            f"{transaction.transaction_date.strftime('%d/%m/%Y')}"
            f" | {amount_label}"
        )
    )
    output_func(
        _format_detail_line(
            "Data valuta",
            transaction.value_date.strftime('%d/%m/%Y'),
            styler=styler,
        )
    )
    output_func(
        _format_detail_line(
            "Descrizione originale",
            transaction.original_description,
            styler=styler,
        )
    )
    if transaction.cleaned_description:
        output_func(
            _format_detail_line(
                "Descrizione pulita",
                transaction.cleaned_description,
                styler=styler,
            )
        )
    output_func(
        _format_detail_line(
            "Categoria proposta",
            styler.prompt(proposed_category),
            styler=styler,
        )
    )

    if prompt_ui is not None and hasattr(prompt_ui, "autocomplete"):
        selected_category = _select_category_with_autocomplete_ui(
            sorted_categories,
            prompt_ui=prompt_ui,
            output_func=output_func,
            styler=styler,
        )
        if selected_category is None:
            return transaction
        return replace(transaction, assigned_category=selected_category)

    while True:
        output_func(
            styler.prompt("Scegli la categoria per questa transazione")
        )
        answer = input_func(
            styler.prompt(
                "Invio = tieni la categoria proposta, "
                "testo = cerca categoria, ? = elenco: "
            )
        ).strip()

        if not answer:
            return transaction

        if answer.casefold() in {"?", "list", "lista", "help"}:
            _print_available_categories(
                sorted_categories,
                output_func=output_func,
                styler=styler,
            )
            continue

        selected_category = _match_category_answer(
            answer,
            sorted_categories,
            output_func=output_func,
            styler=styler,
        )
        if selected_category is not None:
            return replace(
                transaction,
                assigned_category=selected_category,
            )


def _select_category_with_autocomplete_ui(
    sorted_categories: list[str],
    *,
    prompt_ui: PromptUI,
    output_func: Callable[[str], None],
    styler: ReviewStyler,
) -> str | None:
    while True:
        selected_value = prompt_ui.autocomplete(
            (
                "Categoria: digita per cercare, ? per elenco, "
                "Invio per tenere la proposta"
            ),
            sorted_categories,
            default="",
        ).strip()

        if not selected_value:
            return None

        if selected_value.casefold() in {"?", "list", "lista", "help"}:
            _print_available_categories(
                sorted_categories,
                output_func=output_func,
                styler=styler,
            )
            continue

        selected_category = _match_category_answer(
            selected_value,
            sorted_categories,
            output_func=output_func,
            styler=styler,
        )
        if selected_category is not None:
            return selected_category


def _format_detail_line(
    label: str,
    value: str,
    *,
    styler: ReviewStyler,
) -> str:
    return f"  {styler.label(label)}: {value}"


def _sorted_categories(categories: tuple[str, ...]) -> list[str]:
    return sorted(categories, key=str.casefold)


def _print_available_categories(
    categories: list[str],
    *,
    output_func: Callable[[str], None],
    styler: ReviewStyler,
) -> None:
    output_func(styler.label("Categorie disponibili") + ":")
    for line in _format_category_choice_grid(categories, styler=styler):
        output_func(line)


def _match_category_answer(
    answer: str,
    categories: list[str],
    *,
    output_func: Callable[[str], None],
    styler: ReviewStyler,
) -> str | None:
    normalized_answer = answer.strip()
    if not normalized_answer:
        return None

    if normalized_answer.isdigit():
        selected_index = int(normalized_answer)
        if 1 <= selected_index <= len(categories):
            return categories[selected_index - 1]
        output_func(
            "Indice non valido. Scegli un numero presente in lista "
            "oppure usa ? per vedere l'elenco."
        )
        return None

    exact_matches = [
        category for category in categories
        if category.casefold() == normalized_answer.casefold()
    ]
    if exact_matches:
        return exact_matches[0]

    prefix_matches = [
        category for category in categories
        if category.casefold().startswith(normalized_answer.casefold())
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        output_func(
            "Input ambiguo. Categorie compatibili: "
            + ", ".join(prefix_matches)
        )
        return None

    output_func(
        "Categoria non trovata. Digita un prefisso piu' specifico "
        "oppure usa ? per vedere l'elenco."
    )
    return None


def _format_category_choice_grid(
    categories: list[str],
    *,
    styler: ReviewStyler,
) -> list[str]:
    if not categories:
        return []

    plain_labels = [
        f"{index}. {category}"
        for index, category in enumerate(categories, start=1)
    ]
    item_width = max(len(label) for label in plain_labels)
    terminal_width = get_terminal_size(fallback=(100, 20)).columns
    column_width = item_width + 4
    column_count = max(1, min(4, terminal_width // max(column_width, 1)))
    row_count = (len(categories) + column_count - 1) // column_count

    lines: list[str] = []
    for row_index in range(row_count):
        line_parts: list[str] = []
        for column_index in range(column_count):
            choice_index = row_index + (column_index * row_count)
            if choice_index >= len(categories):
                continue
            plain_label = plain_labels[choice_index]
            rendered_label = styler.choice(plain_label, choice_index)
            if styler.enabled:
                line_parts.append(rendered_label)
            else:
                line_parts.append(f"{plain_label:<{item_width}}")
        if styler.enabled:
            lines.append("  " + "    ".join(line_parts))
        else:
            lines.append("  " + "    ".join(line_parts).rstrip())
    return lines


def _confirm_review(
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> bool:
    while True:
        answer = input_func(
            "Confermare il salvataggio su Google Sheets? [y/N]: "
        ).strip().lower()
        if answer in {"y", "yes", "s", "si"}:
            output_func("Conferma registrata.")
            return True
        if answer in {"", "n", "no"}:
            output_func(
                "Operazione annullata. Nessuna scrittura verra' eseguita."
            )
            return False
        output_func("Risposta non valida. Usa 'y' oppure 'n'.")


def _finalize_review(
    reviewed_transactions: list[Transaction],
    category_catalog: CategoryCatalog,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
    prompt_ui: PromptUI | None,
    styler: ReviewStyler,
) -> tuple[list[Transaction], bool]:
    while True:
        _print_review_summary(
            reviewed_transactions,
            output_func=output_func,
            styler=styler,
        )

        if prompt_ui is not None:
            choices = [
                ("__confirm__", "Conferma e salva"),
                ("__cancel__", "Annulla senza scrivere"),
            ]
            choices.extend(
                (
                    f"__edit__:{index}",
                    _build_edit_choice_label(index, transaction),
                )
                for index, transaction in enumerate(
                    reviewed_transactions,
                    start=1,
                )
            )
            selected_value = prompt_ui.select(
                "Scegli l'azione finale",
                choices,
            )
            if selected_value == "__confirm__":
                output_func("Conferma registrata.")
                return reviewed_transactions, True
            if selected_value == "__cancel__":
                output_func(
                    "Operazione annullata. Nessuna scrittura verra' eseguita."
                )
                return reviewed_transactions, False

            selected_index = int(selected_value.split(":", maxsplit=1)[1])
            reviewed_transactions[selected_index - 1] = (
                _review_single_transaction(
                    selected_index,
                    len(reviewed_transactions),
                    reviewed_transactions[selected_index - 1],
                    category_catalog,
                    input_func=input_func,
                    output_func=output_func,
                    prompt_ui=prompt_ui,
                    styler=styler,
                )
            )
            continue

        answer = input_func(
            "Conferma finale: 'y' per salvare, 'n' per annullare, "
            "numero per modificare una transazione: "
        ).strip().lower()

        if answer.isdigit():
            selected_index = int(answer)
            if 1 <= selected_index <= len(reviewed_transactions):
                reviewed_transactions[selected_index - 1] = (
                    _review_single_transaction(
                        selected_index,
                        len(reviewed_transactions),
                        reviewed_transactions[selected_index - 1],
                        category_catalog,
                        input_func=input_func,
                        output_func=output_func,
                        prompt_ui=prompt_ui,
                        styler=styler,
                    )
                )
                continue
            output_func(
                "Indice non valido. Scegli un numero presente nel riepilogo."
            )
            continue

        if answer in {"l", "list"}:
            continue

        if answer in {"y", "yes", "s", "si"}:
            output_func("Conferma registrata.")
            return reviewed_transactions, True

        if answer in {"", "n", "no"}:
            output_func(
                "Operazione annullata. Nessuna scrittura verra' eseguita."
            )
            return reviewed_transactions, False

        output_func(
            "Risposta non valida. Usa 'y', 'n' oppure il numero di una "
            "transazione."
        )


def _print_review_summary(
    reviewed_transactions: list[Transaction],
    *,
    output_func: Callable[[str], None],
    styler: ReviewStyler,
) -> None:
    summary_header = (
        " #  Data       Importo         Categoria           Descrizione"
    )
    summary_rule = (
        " -  ---------- --------------- ------------------- "
        "----------------------------------------"
    )
    output_func("")
    output_func(styler.strong("Riepilogo finale"))
    output_func(styler.muted(summary_header))
    output_func(styler.muted(summary_rule))
    for index, transaction in enumerate(reviewed_transactions, start=1):
        category = transaction.assigned_category or FALLBACK_REVIEW_CATEGORY
        output_func(
            f" {index:>2}  {transaction.value_date.strftime('%d/%m/%Y')} "
            f"{_format_amount(transaction, styler=styler, width=15)} "
            f"{_pad_text(category, width=19)} "
            f"{_compact_text(transaction.original_description, max_length=40)}"
        )


def _build_review_styler(
    *,
    output_func: Callable[[str], None],
) -> ReviewStyler:
    return ReviewStyler(enabled=output_func is print and sys.stdout.isatty())


def _build_edit_choice_label(index: int, transaction: Transaction) -> str:
    assigned_category = (
        transaction.assigned_category or FALLBACK_REVIEW_CATEGORY
    )
    description = _compact_text(
        transaction.original_description,
        max_length=72,
    )
    return (
        "Modifica transazione "
        f"{index}: {assigned_category} | {description}"
    )


def _format_amount(
    transaction: Transaction,
    *,
    styler: ReviewStyler,
    width: int | None = None,
) -> str:
    amount = format(transaction.amount, 'f')
    label = f"{amount} {transaction.currency}"
    if width is not None:
        label = f"{label:>{width}}"
    if transaction.amount > 0:
        return styler.success(label)
    if transaction.amount < 0:
        return styler.danger(label)
    return label


def _compact_text(value: str, *, max_length: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}..."


def _pad_text(value: str, *, width: int) -> str:
    compact = _compact_text(value, max_length=width)
    return f"{compact:<{width}}"


def _build_default_prompt_ui(
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> PromptUI | None:
    if input_func is not input or output_func is not print:
        return None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    try:
        import questionary  # pyright: ignore[reportMissingImports]
    except ModuleNotFoundError:
        return None

    class QuestionaryPromptUI:
        def select(self, message: str, choices: list[tuple[str, str]]) -> str:
            use_shortcuts = len(choices) <= 36
            selected = questionary.select(
                message,
                choices=[
                    questionary.Choice(title=title, value=value)
                    for value, title in choices
                ],
                use_indicator=True,
                use_shortcuts=use_shortcuts,
            ).ask()
            if selected is None:
                raise ReviewCLIError("Interactive selection cancelled")
            return selected

        def autocomplete(
            self,
            message: str,
            choices: list[str],
            default: str = "",
        ) -> str:
            selected = questionary.autocomplete(
                message,
                choices=choices,
                default=default,
                validate=lambda value: True,
            ).ask()
            if selected is None:
                raise ReviewCLIError("Interactive autocomplete cancelled")
            return str(selected)

        def confirm(self, message: str, default: bool = False) -> bool:
            selected = questionary.confirm(message, default=default).ask()
            if selected is None:
                raise ReviewCLIError("Interactive confirmation cancelled")
            return bool(selected)

    return QuestionaryPromptUI()


FALLBACK_REVIEW_CATEGORY = "Da Verificare"
