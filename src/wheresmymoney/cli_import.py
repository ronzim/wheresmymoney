from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from dataclasses import replace

import gspread

from wheresmymoney.categories import CategoryCatalog, CategoryError, load_categories
from wheresmymoney.deterministic_rules import (
    DeterministicRuleError,
    RuleApplicationBatch,
    apply_deterministic_rules,
    load_deterministic_rules,
)
from wheresmymoney.llm_categorizer import FALLBACK_CATEGORY, LLMCategorization, LLMCategorizationBatch, categorize_transactions_with_llm
from wheresmymoney.models import Transaction
from wheresmymoney.parsers import ParsedStatement, ParserError, parse_statement
from wheresmymoney.review_cli import ReviewSessionResult, review_transactions_interactively
from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError
from wheresmymoney.sheet_writer import AppendResult, SheetWriterError, append_transactions_via_gspread
from wheresmymoney.target_config import TargetSheetConfig, TargetSheetConfigError


LOGGER = logging.getLogger(__name__)
ANSI_RESET = "\033[0m"
ANSI_CATEGORY_COLORS = ("\033[96m", "\033[93m")


class ImportCLIError(ValueError):
    pass


@dataclass(frozen=True)
class ImportRunResult:
    parser_name: str
    transaction_count: int
    rule_classified_count: int
    llm_classified_count: int
    confirmed: bool
    append_result: AppendResult | None


def run_import_pipeline(
    file_path: str | Path,
    source_bank: str,
    *,
    dry_run: bool = False,
    llm_attempts: int = 2,
    runtime_config: RuntimeConfig | None = None,
    target_config: TargetSheetConfig | None = None,
    parse_statement_func: Callable[[str | Path, str], ParsedStatement] = parse_statement,
    load_categories_func: Callable[[RuntimeConfig, TargetSheetConfig], CategoryCatalog] = load_categories,
    load_rules_func: Callable[[str | Path, CategoryCatalog], tuple] = load_deterministic_rules,
    apply_rules_func: Callable[[list[Transaction] | tuple[Transaction, ...], list | tuple], RuleApplicationBatch] = apply_deterministic_rules,
    categorize_func: Callable[..., LLMCategorizationBatch] = categorize_transactions_with_llm,
    review_func: Callable[..., ReviewSessionResult] = review_transactions_interactively,
    append_func: Callable[[RuntimeConfig, TargetSheetConfig, str, list[Transaction] | tuple[Transaction, ...]], AppendResult] = append_transactions_via_gspread,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> ImportRunResult:
    runtime = runtime_config or RuntimeConfig.from_env()
    target = target_config or TargetSheetConfig.from_file(runtime.target_sheet_config_path)

    LOGGER.info("Starting import", extra={"file_path": str(file_path), "source_bank": source_bank})
    parsed_statement = parse_statement_func(file_path, source_bank)
    LOGGER.info(
        "Parsing completed",
        extra={
            "parser_name": parsed_statement.parser_name,
            "transaction_count": len(parsed_statement.transactions),
        },
    )
    output_func(
        f"Parsing completato: {len(parsed_statement.transactions)} movimenti con parser {parsed_statement.parser_name}."
    )

    category_catalog = load_categories_func(runtime, target)
    LOGGER.info("Categories loaded", extra={"category_count": len(category_catalog.categories)})

    rules = _load_rules(target, runtime, category_catalog, load_rules_func)
    rule_batch = apply_rules_func(parsed_statement.transactions, rules)
    LOGGER.info(
        "Deterministic rules applied",
        extra={
            "matched_count": len(rule_batch.classified),
            "unmatched_count": len(rule_batch.unmatched),
        },
    )

    llm_batch = _categorize_with_retry(
        rule_batch.unmatched,
        category_catalog,
        runtime,
        categorize_func,
        llm_attempts,
    )
    LOGGER.info("LLM categorization completed", extra={"classified_count": len(llm_batch.classified)})

    classified_transactions = _merge_classified_transactions(
        parsed_statement.transactions,
        rule_batch,
        llm_batch,
    )
    review_result = review_func(
        classified_transactions,
        category_catalog,
        input_func=input_func,
        output_func=output_func,
    )
    LOGGER.info("Review completed", extra={"confirmed": review_result.confirmed})

    if not review_result.confirmed:
        output_func("Import annullato prima della scrittura.")
        return ImportRunResult(
            parser_name=parsed_statement.parser_name,
            transaction_count=len(parsed_statement.transactions),
            rule_classified_count=len(rule_batch.classified),
            llm_classified_count=len(llm_batch.classified),
            confirmed=False,
            append_result=None,
        )

    if dry_run:
        output_func("Dry-run attivo: nessuna scrittura su Google Sheets eseguita.")
        return ImportRunResult(
            parser_name=parsed_statement.parser_name,
            transaction_count=len(parsed_statement.transactions),
            rule_classified_count=len(rule_batch.classified),
            llm_classified_count=len(llm_batch.classified),
            confirmed=True,
            append_result=None,
        )

    append_result = append_func(
        runtime,
        target,
        source_bank,
        review_result.reviewed_transactions,
    )
    LOGGER.info(
        "Append completed",
        extra={
            "worksheet_title": append_result.worksheet_title,
            "start_row": append_result.start_row,
            "row_count": append_result.row_count,
            "updated_range": append_result.updated_range,
        },
    )
    output_func(
        "Append completato: "
        f"{append_result.row_count} righe scritte su {append_result.worksheet_title} "
        f"a partire da {append_result.updated_range}."
    )
    return ImportRunResult(
        parser_name=parsed_statement.parser_name,
        transaction_count=len(parsed_statement.transactions),
        rule_classified_count=len(rule_batch.classified),
        llm_classified_count=len(llm_batch.classified),
        confirmed=True,
        append_result=append_result,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Importa un estratto conto, categoriza i movimenti e li appende su Google Sheets.",
    )
    parser.add_argument("file_path", help="Path del file bancario da importare")
    parser.add_argument(
        "--bank",
        required=True,
        help="Nome del tab bancario di destinazione e identificatore della sorgente",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Esegue parse, classificazione e review senza scrivere su Google Sheets",
    )
    parser.add_argument(
        "--llm-attempts",
        type=int,
        default=2,
        help="Numero massimo di tentativi LLM in caso di errore esterno",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Livello di logging della pipeline",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(message)s",
    )

    try:
        run_import_pipeline(
            args.file_path,
            args.bank,
            dry_run=args.dry_run,
            llm_attempts=args.llm_attempts,
        )
    except DeterministicRuleError as exc:
        print(_format_import_error(exc, use_color=sys.stderr.isatty()), file=sys.stderr)
        return 1
    except (
        CategoryError,
        FileNotFoundError,
        gspread.GSpreadException,
        ImportCLIError,
        ParserError,
        RuntimeConfigError,
        SheetWriterError,
        TargetSheetConfigError,
    ) as exc:
        print(f"Import fallito: {exc}", file=sys.stderr)
        return 1

    return 0


def _format_import_error(exc: Exception, *, use_color: bool) -> str:
    message = f"Import fallito: {exc}"
    if not isinstance(exc, DeterministicRuleError) or not exc.available_categories:
        return message

    categories_block = _format_available_categories(
        exc.available_categories,
        use_color=use_color,
    )
    return f"{message}\nCategorie disponibili nel foglio:\n{categories_block}"


def _format_available_categories(
    categories: tuple[str, ...],
    *,
    use_color: bool,
) -> str:
    sorted_categories = sorted(categories, key=str.casefold)
    lines = []
    for index, category in enumerate(sorted_categories):
        line = f"- {category}"
        if use_color:
            color = ANSI_CATEGORY_COLORS[index % len(ANSI_CATEGORY_COLORS)]
            line = f"{color}{line}{ANSI_RESET}"
        lines.append(line)
    return "\n".join(lines)


def _load_rules(
    target_config: TargetSheetConfig,
    runtime_config: RuntimeConfig,
    category_catalog: CategoryCatalog,
    load_rules_func: Callable[[str | Path, CategoryCatalog], tuple],
) -> tuple:
    if not target_config.deterministic_rules_path:
        return ()

    rules_path = Path(target_config.deterministic_rules_path)
    if not rules_path.is_absolute():
        candidate = runtime_config.target_sheet_config_path.parent.parent / rules_path
        if candidate.exists():
            rules_path = candidate

    return load_rules_func(rules_path, category_catalog)


def _categorize_with_retry(
    transactions: list[Transaction] | tuple[Transaction, ...],
    category_catalog: CategoryCatalog,
    runtime_config: RuntimeConfig,
    categorize_func: Callable[..., LLMCategorizationBatch],
    llm_attempts: int,
) -> LLMCategorizationBatch:
    if not transactions:
        return LLMCategorizationBatch(classified=())

    attempts = max(1, llm_attempts)
    classified = []
    for transaction in transactions:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                batch = categorize_func([transaction], category_catalog, runtime_config)
                classified.extend(batch.classified)
                break
            except Exception as exc:  # retry is only for external LLM call failures
                last_error = exc
                LOGGER.warning(
                    "LLM categorization attempt failed",
                    extra={
                        "attempt": attempt,
                        "attempts": attempts,
                        "error": str(exc),
                        "original_description": transaction.original_description,
                    },
                )
                if attempt == attempts:
                    LOGGER.error(
                        "LLM categorization degraded to fallback",
                        extra={
                            "attempts": attempts,
                            "error": str(last_error),
                            "original_description": transaction.original_description,
                        },
                    )
                    classified.append(
                        LLMCategorization(
                            transaction=replace(
                                transaction,
                                assigned_category=FALLBACK_CATEGORY,
                                cleaned_description=transaction.original_description.strip(),
                            ),
                            classification_source="llm_retry_fallback",
                            raw_response=str(last_error),
                        )
                    )

    return LLMCategorizationBatch(classified=tuple(classified))


def _merge_classified_transactions(
    original_transactions: tuple[Transaction, ...],
    rule_batch: RuleApplicationBatch,
    llm_batch: LLMCategorizationBatch,
) -> tuple[Transaction, ...]:
    classified_lookup: dict[tuple, deque[Transaction]] = defaultdict(deque)

    for application in rule_batch.classified:
        classified_lookup[_transaction_fingerprint(application.transaction)].append(
            application.transaction
        )
    for application in llm_batch.classified:
        classified_lookup[_transaction_fingerprint(application.transaction)].append(
            application.transaction
        )

    merged: list[Transaction] = []
    for transaction in original_transactions:
        fingerprint = _transaction_fingerprint(transaction)
        if not classified_lookup[fingerprint]:
            raise ImportCLIError(
                "Classification pipeline returned an incomplete transaction set"
            )
        merged.append(classified_lookup[fingerprint].popleft())

    return tuple(merged)


def _transaction_fingerprint(transaction: Transaction) -> tuple:
    return (
        transaction.source_bank,
        transaction.transaction_date,
        transaction.value_date,
        transaction.amount,
        transaction.currency,
        transaction.original_description,
        transaction.raw_row_id,
    )