from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.llm_categorizer import (
    FALLBACK_CATEGORY,
    SimilarTransactionExample,
    build_categorization_prompt,
    categorize_transactions_with_llm,
    parse_llm_json,
)
from wheresmymoney.models import Transaction
from wheresmymoney.runtime_config import RuntimeConfig


def _runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        google_service_account_json=None,
        gemini_api_key="test-key",
        target_sheet_config_path=Path("config/target_sheet.example.json"),
        gemini_model="gemini-2.5-flash",
    )


def test_parse_llm_json_accepts_plain_json() -> None:
    parsed = parse_llm_json(
        '{"assigned_category": "Mutuo", "cleaned_description": "Rata mutuo"}'
    )

    assert parsed["assigned_category"] == "Mutuo"
    assert parsed["cleaned_description"] == "Rata mutuo"


def test_parse_llm_json_accepts_fenced_json() -> None:
    parsed = parse_llm_json(
        '```json\n{"assigned_category": "Spesa", "cleaned_description": "Supermercato"}\n```'
    )

    assert parsed["assigned_category"] == "Spesa"


def test_build_categorization_prompt_includes_structured_context_and_examples() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="01/01/2026",
        value_date="02/01/2026",
        amount="-100,00",
        currency="EUR",
        original_description="addebito mutuo gennaio",
    )
    examples = (
        SimilarTransactionExample(
            source_bank="Lisa",
            amount=Decimal("-100.00"),
            currency="EUR",
            original_description="addebito mutuo dicembre",
            assigned_category="Mutuo",
            value_date="02/12/2025",
        ),
    )

    prompt = build_categorization_prompt(
        transaction,
        catalog,
        similar_examples=examples,
    )

    assert '"source_bank": "Lisa"' in prompt
    assert '"amount": "-100.00"' in prompt
    assert '"assigned_category": "Mutuo"' in prompt
    assert '"original_description": "addebito mutuo dicembre"' in prompt


def test_categorize_transactions_with_llm_uses_valid_response() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = _runtime_config()
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="01/01/2026",
        value_date="01/01/2026",
        amount="-100,00",
        currency="EUR",
        original_description="addebito mutuo gennaio",
    )

    def responder(_prompt: str, _model: str) -> str:
        return '{"assigned_category": "Mutuo", "cleaned_description": "Rata mutuo gennaio"}'

    result = categorize_transactions_with_llm(
        [transaction],
        catalog,
        runtime,
        responder=responder,
    )

    assert result.classified[0].classification_source == "llm"
    assert result.classified[0].transaction.assigned_category == "Mutuo"
    assert result.classified[0].transaction.cleaned_description == "Rata mutuo gennaio"


def test_categorize_transactions_with_llm_falls_back_on_invalid_category() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = _runtime_config()
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="01/01/2026",
        value_date="01/01/2026",
        amount="-20,00",
        currency="EUR",
        original_description="spesa strana",
    )

    def responder(_prompt: str, _model: str) -> str:
        return '{"assigned_category": "NonEsiste", "cleaned_description": "Spesa strana"}'

    result = categorize_transactions_with_llm(
        [transaction],
        catalog,
        runtime,
        responder=responder,
    )

    assert result.classified[0].classification_source == "llm_fallback"
    assert result.classified[0].transaction.assigned_category == FALLBACK_CATEGORY
    assert result.classified[0].transaction.cleaned_description == "spesa strana"


def test_categorize_transactions_with_llm_falls_back_on_invalid_json() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = _runtime_config()
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="01/01/2026",
        value_date="01/01/2026",
        amount="-20,00",
        currency="EUR",
        original_description="  descrizione con spazi  ",
    )

    def responder(_prompt: str, _model: str) -> str:
        return 'not-json'

    result = categorize_transactions_with_llm(
        [transaction],
        catalog,
        runtime,
        responder=responder,
    )

    assert result.classified[0].classification_source == "llm_fallback"
    assert result.classified[0].transaction.assigned_category == FALLBACK_CATEGORY
    assert result.classified[0].transaction.cleaned_description == "descrizione con spazi"


def test_categorize_transactions_with_llm_passes_similar_examples_to_prompt() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = _runtime_config()
    transaction = Transaction(
        source_bank="Lisa",
        transaction_date="01/01/2026",
        value_date="01/01/2026",
        amount="-20,00",
        currency="EUR",
        original_description="spesa supermercato quartiere",
    )
    captured_prompts: list[str] = []

    def responder(prompt: str, _model: str) -> str:
        captured_prompts.append(prompt)
        return '{"assigned_category": "Spesa", "cleaned_description": "Supermercato"}'

    def similar_examples_provider(_transaction: Transaction) -> tuple[SimilarTransactionExample, ...]:
        return (
            SimilarTransactionExample(
                source_bank="Lisa",
                amount=Decimal("-19.90"),
                currency="EUR",
                original_description="spesa supermercato centro",
                assigned_category="Spesa",
                value_date="15/12/2025",
            ),
        )

    categorize_transactions_with_llm(
        [transaction],
        catalog,
        runtime,
        responder=responder,
        similar_examples_provider=similar_examples_provider,
    )

    assert captured_prompts
    assert '"similar_examples": [' in captured_prompts[0]
    assert '"original_description": "spesa supermercato centro"' in captured_prompts[0]


def test_categorize_transactions_with_llm_batches_multiple_transactions() -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = _runtime_config()
    transactions = [
        Transaction(
            source_bank="Lisa",
            transaction_date="01/01/2026",
            value_date="01/01/2026",
            amount="-100,00",
            currency="EUR",
            original_description="addebito mutuo gennaio",
        ),
        Transaction(
            source_bank="Lisa",
            transaction_date="02/01/2026",
            value_date="02/01/2026",
            amount="-45,20",
            currency="EUR",
            original_description="spesa supermercato",
        ),
    ]
    captured_prompts: list[str] = []

    def responder(prompt: str, _model: str) -> str:
        captured_prompts.append(prompt)
        return (
            '{"classifications": ['
            '{"transaction_index": 0, "assigned_category": "Mutuo", "cleaned_description": "Rata mutuo gennaio"}, '
            '{"transaction_index": 1, "assigned_category": "Spesa", "cleaned_description": "Supermercato"}'
            ']}'
        )

    result = categorize_transactions_with_llm(
        transactions,
        catalog,
        runtime,
        responder=responder,
    )

    assert len(captured_prompts) == 1
    assert '"transaction_index": 0' in captured_prompts[0]
    assert '"transaction_index": 1' in captured_prompts[0]
    assert '"original_description": "addebito mutuo gennaio"' in captured_prompts[0]
    assert '"original_description": "spesa supermercato"' in captured_prompts[0]
    assert result.classified[0].classification_source == "llm"
    assert result.classified[0].transaction.assigned_category == "Mutuo"
    assert result.classified[1].classification_source == "llm"
    assert result.classified[1].transaction.assigned_category == "Spesa"


def test_categorize_transactions_with_llm_logs_batch_progress(caplog) -> None:
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")
    runtime = RuntimeConfig(
        google_service_account_json=None,
        gemini_api_key="test-key",
        target_sheet_config_path=Path("config/target_sheet.example.json"),
        gemini_model="gemini-2.5-flash",
        gemini_batch_size=1,
    )
    transactions = [
        Transaction(
            source_bank="Lisa",
            transaction_date="01/01/2026",
            value_date="01/01/2026",
            amount="-100,00",
            currency="EUR",
            original_description="addebito mutuo gennaio",
        ),
        Transaction(
            source_bank="Lisa",
            transaction_date="02/01/2026",
            value_date="02/01/2026",
            amount="-45,20",
            currency="EUR",
            original_description="spesa supermercato",
        ),
    ]

    def responder(prompt: str, _model: str) -> str:
        if '"transaction_index": 0' in prompt:
            return '{"classifications": [{"transaction_index": 0, "assigned_category": "Mutuo", "cleaned_description": "Rata mutuo gennaio"}]}'
        return '{"classifications": [{"transaction_index": 0, "assigned_category": "Spesa", "cleaned_description": "Supermercato"}]}'

    with caplog.at_level(logging.INFO, logger="wheresmymoney.llm_categorizer"):
        categorize_transactions_with_llm(
            transactions,
            catalog,
            runtime,
            responder=responder,
        )

    send_records = [
        record for record in caplog.records if record.msg == "Invio batch LLM %s/%s (%s)"
    ]
    completed_records = [
        record
        for record in caplog.records
        if record.msg == "Batch LLM %s/%s completato (%s), fallback=%s"
    ]

    assert len(send_records) == 2
    assert len(completed_records) == 2
    assert "Invio batch LLM 1/2 (1-1/2)" in caplog.text
    assert "Invio batch LLM 2/2 (2-2/2)" in caplog.text
    assert "Batch LLM 1/2 completato (1-1/2), fallback=0" in caplog.text
    assert "Batch LLM 2/2 completato (2-2/2), fallback=0" in caplog.text
    assert send_records[0].transaction_range == "1-1/2"
    assert send_records[1].transaction_range == "2-2/2"
    assert completed_records[0].request_succeeded is True
    assert completed_records[1].request_succeeded is True