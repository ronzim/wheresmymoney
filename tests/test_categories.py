from __future__ import annotations

import pytest

from wheresmymoney.categories import CategoryError, build_category_catalog


def test_build_category_catalog_skips_header_and_blanks() -> None:
    catalog = build_category_catalog(
        ["Categorie", "", "Spesa", "Mutuo", " Viaggi ", ""],
        header_name="Categorie",
    )

    assert catalog.categories == ("Spesa", "Mutuo", "Viaggi")


def test_build_category_catalog_rejects_duplicates() -> None:
    with pytest.raises(CategoryError, match="Duplicate category"):
        build_category_catalog(
            ["Categorie", "Spesa", "Mutuo", "Spesa"],
            header_name="Categorie",
        )


def test_build_category_catalog_requires_at_least_one_category() -> None:
    with pytest.raises(CategoryError, match="No categories found"):
        build_category_catalog(["Categorie", "", "  "], header_name="Categorie")