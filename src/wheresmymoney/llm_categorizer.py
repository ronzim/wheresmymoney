from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable

from wheresmymoney.categories import CategoryCatalog, CategoryError
from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError


FALLBACK_CATEGORY = "Da Verificare"


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

    for transaction in transactions:
        similar_examples = tuple(similar_examples_provider(transaction)) if similar_examples_provider else ()
        prompt = build_categorization_prompt(
            transaction,
            category_catalog,
            similar_examples=similar_examples,
        )
        raw_response = effective_responder(prompt, runtime_config.gemini_model)
        classified.append(
            _classify_single_transaction(
                transaction,
                raw_response,
                category_catalog,
            )
        )

    return LLMCategorizationBatch(classified=tuple(classified))


def build_categorization_prompt(
    transaction: Transaction,
    category_catalog: CategoryCatalog,
    *,
    similar_examples: tuple[SimilarTransactionExample, ...] = (),
) -> str:
    categories = "\n".join(f"- {category}" for category in category_catalog.categories)
    context_payload = {
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
    return (
        "Sei un analista finanziario.\n"
        "Rispondi con solo JSON valido, senza markdown e senza testo extra.\n"
        "Il JSON deve avere esattamente queste chiavi:"
        ' "assigned_category", "cleaned_description".\n'
        "assigned_category deve essere una delle categorie ammesse.\n"
        "cleaned_description deve essere una breve descrizione leggibile, ma il testo originale non verra' sovrascritto nel foglio.\n"
        "Usa il contesto strutturato disponibile: banca, date, importo, segno e, se presenti, esempi storici simili gia' classificati.\n"
        "Categorie ammesse:\n"
        f"{categories}\n\n"
        "Contesto transazione (JSON):\n"
        f"{json.dumps(context_payload, ensure_ascii=False, indent=2)}\n"
    )


def parse_llm_json(raw_response: str) -> dict[str, str]:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise LLMCategorizerError("LLM response must be a non-empty string")

    payload = raw_response.strip()
    if payload.startswith("```"):
        payload = _strip_code_fences(payload)

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMCategorizerError("LLM response is not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise LLMCategorizerError("LLM response JSON must be an object")

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
            raw_response=raw_response,
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