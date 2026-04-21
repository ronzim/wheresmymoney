from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from wheresmymoney.categories import CategoryError, CategoryCatalog
from wheresmymoney.models import Transaction


class DeterministicRuleError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        available_categories: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.available_categories = available_categories


@dataclass(frozen=True)
class DeterministicRule:
    contains: str
    category: str

    def __post_init__(self) -> None:
        if not isinstance(self.contains, str) or not self.contains.strip():
            raise DeterministicRuleError("Rule 'contains' must be a non-empty string")
        if not isinstance(self.category, str) or not self.category.strip():
            raise DeterministicRuleError("Rule 'category' must be a non-empty string")
        object.__setattr__(self, "contains", self.contains.strip())
        object.__setattr__(self, "category", self.category.strip())

    def matches(self, transaction: Transaction) -> bool:
        haystack = transaction.original_description.casefold()
        return self.contains.casefold() in haystack


@dataclass(frozen=True)
class RuleApplication:
    transaction: Transaction
    matched_rule: DeterministicRule | None
    classification_source: str


@dataclass(frozen=True)
class RuleApplicationBatch:
    classified: tuple[RuleApplication, ...]
    unmatched: tuple[Transaction, ...]


@dataclass(frozen=True)
class RuleLoadResult:
    rules: tuple[DeterministicRule, ...]
    skipped_rules: tuple[str, ...] = ()


def load_deterministic_rules(
    file_path: str | Path,
    category_catalog: CategoryCatalog,
) -> tuple[DeterministicRule, ...]:
    return load_deterministic_rules_report(file_path, category_catalog).rules


def load_deterministic_rules_report(
    file_path: str | Path,
    category_catalog: CategoryCatalog,
    *,
    skip_unknown_categories: bool = False,
) -> RuleLoadResult:
    path = Path(file_path)
    try:
        raw_config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeterministicRuleError(f"Rules file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeterministicRuleError(f"Invalid JSON in rules file: {path}") from exc

    raw_rules = raw_config.get("rules")
    if not isinstance(raw_rules, list):
        raise DeterministicRuleError("Rules file must contain a 'rules' list")

    rules: list[DeterministicRule] = []
    skipped_rules: list[str] = []
    seen_contains: set[str] = set()
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise DeterministicRuleError("Each rule must be a JSON object")
        contains = raw_rule.get("contains", "")
        category_name = raw_rule.get("category", "")
        try:
            category = category_catalog.ensure_valid(category_name)
        except CategoryError as exc:
            if skip_unknown_categories:
                skipped_rules.append(
                    f"{contains} -> {category_name}"
                )
                continue
            raise DeterministicRuleError(
                "Unknown category in deterministic rule: "
                f"contains={contains!r}, category={category_name!r}",
                available_categories=tuple(category_catalog.categories),
            ) from exc
        rule = DeterministicRule(
            contains=contains,
            category=category,
        )
        fingerprint = rule.contains.casefold()
        if fingerprint in seen_contains:
            raise DeterministicRuleError(
                f"Duplicate deterministic rule condition: {rule.contains}"
            )
        seen_contains.add(fingerprint)
        rules.append(rule)

    return RuleLoadResult(
        rules=tuple(rules),
        skipped_rules=tuple(skipped_rules),
    )


def apply_deterministic_rules(
    transactions: list[Transaction] | tuple[Transaction, ...],
    rules: list[DeterministicRule] | tuple[DeterministicRule, ...],
) -> RuleApplicationBatch:
    classified: list[RuleApplication] = []
    unmatched: list[Transaction] = []

    for transaction in transactions:
        matched_rule = _find_matching_rule(transaction, rules)
        if matched_rule is None:
            unmatched.append(transaction)
            continue

        classified_transaction = replace(
            transaction,
            assigned_category=matched_rule.category,
        )
        classified.append(
            RuleApplication(
                transaction=classified_transaction,
                matched_rule=matched_rule,
                classification_source="rule",
            )
        )

    return RuleApplicationBatch(
        classified=tuple(classified),
        unmatched=tuple(unmatched),
    )


def _find_matching_rule(
    transaction: Transaction,
    rules: list[DeterministicRule] | tuple[DeterministicRule, ...],
) -> DeterministicRule | None:
    for rule in rules:
        if rule.matches(transaction):
            return rule
    return None