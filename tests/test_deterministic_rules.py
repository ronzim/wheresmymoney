from __future__ import annotations

from pathlib import Path

import pytest

from wheresmymoney.categories import build_category_catalog
from wheresmymoney.deterministic_rules import (
    DeterministicRuleError,
    apply_deterministic_rules,
    load_deterministic_rules,
)
from wheresmymoney.models import Transaction


def test_load_deterministic_rules_validates_categories(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        '{"rules": [{"contains": "MUTUO", "category": "Mutuo"}]}'
    )
    catalog = build_category_catalog(["Categorie", "Mutuo", "Spesa"], header_name="Categorie")

    rules = load_deterministic_rules(rules_path, catalog)

    assert len(rules) == 1
    assert rules[0].contains == "MUTUO"
    assert rules[0].category == "Mutuo"


def test_load_deterministic_rules_rejects_unknown_category(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        '{"rules": [{"contains": "MUTUO", "category": "NonEsiste"}]}'
    )
    catalog = build_category_catalog(["Categorie", "Mutuo"], header_name="Categorie")

    with pytest.raises(
        DeterministicRuleError,
        match=r"contains='MUTUO', category='NonEsiste'",
    ):
        load_deterministic_rules(rules_path, catalog)


def test_apply_deterministic_rules_classifies_and_tracks_source(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        '{"rules": ['
        '{"contains": "MUTUO", "category": "Mutuo"},'
        '{"contains": "SUPERMERCATO", "category": "Spesa"}'
        ']}'
    )
    catalog = build_category_catalog(
        ["Categorie", "Mutuo", "Spesa", "Viaggi"],
        header_name="Categorie",
    )
    rules = load_deterministic_rules(rules_path, catalog)

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
            transaction_date="01/01/2026",
            value_date="01/01/2026",
            amount="-20,00",
            currency="EUR",
            original_description="spesa supermercato quartiere",
        ),
        Transaction(
            source_bank="Lisa",
            transaction_date="01/01/2026",
            value_date="01/01/2026",
            amount="-30,00",
            currency="EUR",
            original_description="biglietto treno",
        ),
    ]

    result = apply_deterministic_rules(transactions, rules)

    assert len(result.classified) == 2
    assert len(result.unmatched) == 1
    assert result.classified[0].transaction.assigned_category == "Mutuo"
    assert result.classified[0].classification_source == "rule"
    assert result.classified[1].transaction.assigned_category == "Spesa"
    assert result.unmatched[0].original_description == "biglietto treno"