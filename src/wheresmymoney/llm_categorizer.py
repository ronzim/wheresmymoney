from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Callable

from wheresmymoney.categories import CategoryCatalog, CategoryError
from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError


FALLBACK_CATEGORY = "Da Verificare"
HOUSEHOLD_SPENDING_CONTEXT = (
    "Contesto famiglia utile per orientarti nelle spese:\n"
    "- Lisa lavora in centro a Bergamo, davanti al PAM, dove va spesso a pranzo.\n"
    "- Mattia lavora a Dalmine e mangia spesso dal kebabbaro, all'Anonimo o al Lavetti.\n"
    "- La spesa settimanale di solito viene fatta alla Conad di Curno o a volte a Brembate Sopra.\n"
    "- In famiglia c'e' un cane di nome Linus.\n"
)
LOGGER = logging.getLogger(__name__)


class LLMCategorizerError(ValueError):
    pass


@dataclass(frozen=True)
class LLMCategorization:
    transaction: Transaction
    classification_source: str
    raw_response: str


@dataclass(frozen=True)
class SimilarTransactionExample:
    source_bank: str
    amount: Decimal
    currency: str
    original_description: str
    assigned_category: str
    value_date: str | None = None


@dataclass(frozen=True)
class LLMCategorizationBatch:
    classified: tuple[LLMCategorization, ...]


def categorize_transactions_with_llm(
    transactions: list[Transaction] | tuple[Transaction, ...],
    category_catalog: CategoryCatalog,
    runtime_config: RuntimeConfig,
    *,
    responder: Callable[[str, str], str] | None = None,
    similar_examples_provider: Callable[[Transaction], list[SimilarTransactionExample] | tuple[SimilarTransactionExample, ...]] | None = None,
) -> LLMCategorizationBatch:
    if runtime_config.gemini_api_key is None:
        raise RuntimeConfigError(
            "GEMINI_API_KEY is required to run LLM categorization"
        )

    effective_responder = responder or _default_responder(runtime_config)
    classified: list[LLMCategorization] = []

    transactions_batch = tuple(transactions)
    if not transactions_batch:
        return LLMCategorizationBatch(classified=())

    transaction_chunks = _chunk_transactions(
        transactions_batch,
        runtime_config.gemini_batch_size,
    )
    total_batches = len(transaction_chunks)
    total_transactions = len(transactions_batch)

    for batch_index, transaction_chunk in enumerate(transaction_chunks, start=1):
        batch_start = sum(len(chunk) for chunk in transaction_chunks[: batch_index - 1]) + 1
        batch_end = batch_start + len(transaction_chunk) - 1
        similar_examples_batch = tuple(
            tuple(similar_examples_provider(transaction))
            if similar_examples_provider
            else ()
            for transaction in transaction_chunk
        )
        prompt = build_categorization_batch_prompt(
            transaction_chunk,
            category_catalog,
            similar_examples_by_transaction=similar_examples_batch,
        )

        LOGGER.info(
            "Invio batch LLM %s/%s (%s)",
            batch_index,
            total_batches,
            f"{batch_start}-{batch_end}/{total_transactions}",
            extra={
                "batch_index": batch_index,
                "batch_count": total_batches,
                "batch_size": len(transaction_chunk),
                "transaction_range": f"{batch_start}-{batch_end}/{total_transactions}",
                "gemini_model": runtime_config.gemini_model,
            },
        )

        try:
            raw_response = effective_responder(prompt, runtime_config.gemini_model)
        except Exception:
            LOGGER.warning(
                "Batch LLM %s/%s fallito (%s)",
                batch_index,
                total_batches,
                f"{batch_start}-{batch_end}/{total_transactions}",
                exc_info=True,
                extra={
                    "batch_index": batch_index,
                    "batch_count": total_batches,
                    "batch_size": len(transaction_chunk),
                    "transaction_range": f"{batch_start}-{batch_end}/{total_transactions}",
                },
            )
            raise

        try:
            parsed_batch = parse_llm_json_batch(
                raw_response,
                expected_count=len(transaction_chunk),
            )
            fallback_count = sum(item is None for item in parsed_batch)
            LOGGER.info(
                "Batch LLM %s/%s completato (%s), fallback=%s",
                batch_index,
                total_batches,
                f"{batch_start}-{batch_end}/{total_transactions}",
                fallback_count,
                extra={
                    "batch_index": batch_index,
                    "batch_count": total_batches,
                    "batch_size": len(transaction_chunk),
                    "transaction_range": f"{batch_start}-{batch_end}/{total_transactions}",
                    "request_succeeded": True,
                    "fallback_count": fallback_count,
                },
            )
        except LLMCategorizerError:
            parsed_batch = (None,) * len(transaction_chunk)
            LOGGER.warning(
                "Batch LLM %s/%s completato con fallback totale (%s)",
                batch_index,
                total_batches,
                f"{batch_start}-{batch_end}/{total_transactions}",
                extra={
                    "batch_index": batch_index,
                    "batch_count": total_batches,
                    "batch_size": len(transaction_chunk),
                    "transaction_range": f"{batch_start}-{batch_end}/{total_transactions}",
                    "request_succeeded": True,
                    "fallback_count": len(transaction_chunk),
                },
            )

        for transaction, parsed_item in zip(transaction_chunk, parsed_batch):
            classified.append(
                _classify_single_transaction_from_parsed(
                    transaction,
                    parsed_item,
                    raw_response,
                    category_catalog,
                )
            )

    return LLMCategorizationBatch(classified=tuple(classified))


def build_categorization_batch_prompt(
    transactions: tuple[Transaction, ...],
    category_catalog: CategoryCatalog,
    *,
    similar_examples_by_transaction: tuple[
        tuple[SimilarTransactionExample, ...], ...
    ] = (),
) -> str:
    categories = "\n".join(f"- {category}" for category in category_catalog.categories)
    effective_examples = similar_examples_by_transaction or tuple(() for _ in transactions)
    contexts = [
        {
            "transaction_index": index,
            **_build_transaction_context(transaction, similar_examples),
        }
        for index, (transaction, similar_examples) in enumerate(
            zip(transactions, effective_examples)
        )
    ]
    return (
        "Sei un analista finanziario.\n"
        "Rispondi con solo JSON valido, senza markdown e senza testo extra.\n"
        "Il JSON deve essere un oggetto con una sola chiave: \"classifications\".\n"
        "classifications deve contenere una lista con una voce per ogni transazione.\n"
        'Ogni voce deve avere esattamente queste chiavi: "transaction_index", "assigned_category", "cleaned_description".\n'
        "transaction_index deve corrispondere all'indice della transazione nel contesto fornito.\n"
        "assigned_category deve essere una delle categorie ammesse.\n"
        "cleaned_description deve essere una breve descrizione leggibile, ma il testo originale non verra' sovrascritto nel foglio.\n"
        "Usa il contesto strutturato disponibile: banca, date, importo, segno e, se presenti, esempi storici simili gia' classificati.\n"
        f"{HOUSEHOLD_SPENDING_CONTEXT}"
        "Categorie ammesse:\n"
        f"{categories}\n\n"
        "Contesto transazioni (JSON):\n"
        f"{json.dumps(contexts, ensure_ascii=False, indent=2)}\n"
    )


def build_categorization_prompt(
    transaction: Transaction,
    category_catalog: CategoryCatalog,
    *,
    similar_examples: tuple[SimilarTransactionExample, ...] = (),
) -> str:
    return build_categorization_batch_prompt(
        (transaction,),
        category_catalog,
        similar_examples_by_transaction=(similar_examples,),
    )


def _build_transaction_context(
    transaction: Transaction,
    similar_examples: tuple[SimilarTransactionExample, ...],
) -> dict[str, Any]:
    return {
        "source_bank": transaction.source_bank,
        "transaction_date": transaction.transaction_date.strftime("%d/%m/%Y"),
        "value_date": transaction.value_date.strftime("%d/%m/%Y"),
        "amount": format(transaction.amount, "f"),
        "currency": transaction.currency,
        "original_description": transaction.original_description,
        "similar_examples": [
            {
                "source_bank": example.source_bank,
                "amount": format(example.amount, "f"),
                "currency": example.currency,
                "original_description": example.original_description,
                "assigned_category": example.assigned_category,
                **(
                    {"value_date": example.value_date}
                    if example.value_date is not None
                    else {}
                ),
            }
            for example in similar_examples
        ],
    }

def parse_llm_json(raw_response: str) -> dict[str, str]:
    parsed = _load_llm_payload(raw_response)
    if not isinstance(parsed, dict):
        raise LLMCategorizerError("LLM response JSON must be an object")

    return _validate_llm_item(parsed)


def parse_llm_json_batch(
    raw_response: str,
    *,
    expected_count: int,
) -> tuple[dict[str, str] | None, ...]:
    parsed = _load_llm_payload(raw_response)

    if isinstance(parsed, dict):
        if "classifications" in parsed:
            parsed = parsed["classifications"]
        elif expected_count == 1:
            return (_validate_llm_item(parsed),)
        else:
            raise LLMCategorizerError(
                "LLM batch response JSON must contain a classifications list"
            )

    if not isinstance(parsed, list):
        raise LLMCategorizerError("LLM batch response JSON must be a list")

    parsed_items: list[dict[str, str] | None] = [None] * expected_count
    seen_indexes: set[int] = set()

    for position, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue

        raw_index = item.get("transaction_index", position)
        if (
            not isinstance(raw_index, int)
            or raw_index < 0
            or raw_index >= expected_count
            or raw_index in seen_indexes
        ):
            continue

        try:
            parsed_items[raw_index] = _validate_llm_item(item)
            seen_indexes.add(raw_index)
        except LLMCategorizerError:
            continue

    return tuple(parsed_items)


def _load_llm_payload(raw_response: str) -> Any:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise LLMCategorizerError("LLM response must be a non-empty string")

    payload = raw_response.strip()
    if payload.startswith("```"):
        payload = _strip_code_fences(payload)

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMCategorizerError("LLM response is not valid JSON") from exc


def _validate_llm_item(parsed: dict[str, Any]) -> dict[str, str]:
    category = parsed.get("assigned_category")
    cleaned_description = parsed.get("cleaned_description")
    if not isinstance(category, str) or not category.strip():
        raise LLMCategorizerError("assigned_category must be a non-empty string")
    if not isinstance(cleaned_description, str) or not cleaned_description.strip():
        raise LLMCategorizerError("cleaned_description must be a non-empty string")

    return {
        "assigned_category": category.strip(),
        "cleaned_description": cleaned_description.strip(),
    }


def _classify_single_transaction(
    transaction: Transaction,
    raw_response: str,
    category_catalog: CategoryCatalog,
) -> LLMCategorization:
    try:
        parsed = parse_llm_json(raw_response)
        return _classify_single_transaction_from_parsed(
            transaction,
            parsed,
            raw_response,
            category_catalog,
        )
    except LLMCategorizerError:
        return _classify_single_transaction_from_parsed(
            transaction,
            None,
            raw_response,
            category_catalog,
        )


def _classify_single_transaction_from_parsed(
    transaction: Transaction,
    parsed: dict[str, str] | None,
    raw_response: str,
    category_catalog: CategoryCatalog,
) -> LLMCategorization:
    try:
        if parsed is None:
            raise LLMCategorizerError("Missing parsed LLM classification")
        category = category_catalog.ensure_valid(parsed["assigned_category"])
        cleaned_description = parsed["cleaned_description"]
        classified_transaction = replace(
            transaction,
            assigned_category=category,
            cleaned_description=cleaned_description,
        )
        return LLMCategorization(
            transaction=classified_transaction,
            classification_source="llm",
            raw_response=json.dumps(parsed, ensure_ascii=False),
        )
    except (LLMCategorizerError, CategoryError):
        fallback_transaction = replace(
            transaction,
            assigned_category=FALLBACK_CATEGORY,
            cleaned_description=_safe_cleaned_description(transaction),
        )
        return LLMCategorization(
            transaction=fallback_transaction,
            classification_source="llm_fallback",
            raw_response=raw_response,
        )


def _safe_cleaned_description(transaction: Transaction) -> str:
    return transaction.original_description.strip()


def _strip_code_fences(payload: str) -> str:
    stripped = payload.strip()
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _default_responder(
    runtime_config: RuntimeConfig,
) -> Callable[[str, str], str]:
    from google import genai

    client = genai.Client(api_key=runtime_config.gemini_api_key)

    def responder(prompt: str, model_name: str) -> str:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return response.text or ""

    return responder


def _chunk_transactions(
    transactions: tuple[Transaction, ...],
    batch_size: int,
) -> tuple[tuple[Transaction, ...], ...]:
    return tuple(
        transactions[start : start + batch_size]
        for start in range(0, len(transactions), batch_size)
    )