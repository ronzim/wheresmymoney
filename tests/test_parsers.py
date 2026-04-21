from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from wheresmymoney.parsers import detect_parser, parse_statement


TEST_DATA = Path(__file__).resolve().parents[1] / "test-data"


def test_detect_structured_xlsx_parser() -> None:
    parser_name = detect_parser(TEST_DATA / "Lista Movimenti_CAI_20260102160759.xlsx")
    assert parser_name == "structured_xlsx"


def test_parse_structured_xlsx_statement() -> None:
    parsed = parse_statement(
        TEST_DATA / "Lista Movimenti_CAI_20260102160759.xlsx",
        source_bank="Comune_ca",
    )

    assert parsed.parser_name == "structured_xlsx"
    assert parsed.transactions[0].source_bank == "Comune_ca"
    assert parsed.transactions[0].amount == Decimal("-454.00")
    assert parsed.transactions[0].currency == "EUR"
    assert parsed.transactions[0].original_description.startswith(
        "00760 LOZZA LISA RONZONI"
    )


def test_detect_html_xls_parser() -> None:
    parser_name = detect_parser(TEST_DATA / "movimentiConto-1.xls")
    assert parser_name == "html_xls"


def test_parse_html_xls_statement() -> None:
    parsed = parse_statement(
        TEST_DATA / "movimentiConto-1.xls",
        source_bank="Mattia",
    )

    assert parsed.parser_name == "html_xls"
    assert parsed.transactions[0].source_bank == "Mattia"
    assert parsed.transactions[0].amount == Decimal("3450.00")
    assert parsed.transactions[0].currency == "EUR"
    assert parsed.transactions[0].original_description == (
        "acc.emolum.(stp.pen) - bon.da d/vision lab s.r.l. stipendio novembre 2025"
    )


def test_detect_split_amount_xlsx_parser() -> None:
    parser_name = detect_parser(TEST_DATA / "ListaMovimenti.xlsx")
    assert parser_name == "split_amount_xlsx"


def test_parse_split_amount_xlsx_statement() -> None:
    parsed = parse_statement(
        TEST_DATA / "ListaMovimenti.xlsx",
        source_bank="Lisa",
    )

    assert parsed.parser_name == "split_amount_xlsx"
    assert parsed.transactions[0].amount == Decimal("-15000.00")
    assert parsed.transactions[0].currency == "EUR"
    assert parsed.transactions[0].original_description == (
        "BONIFICO SEPA ISTANTANEO TRN CCTX00000263913948 BENEF. Lozza Lisa Ronzoni Mattia PER giroconto"
    )
    assert parsed.transactions[3].amount == Decimal("30.00")