from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from wheresmymoney.parsers import detect_parser, parse_statement


TEST_DATA = Path(__file__).resolve().parents[1] / "test-data"


def test_detect_structured_xlsx_parser() -> None:
    parser_name = detect_parser(
        TEST_DATA / "Lista Movimenti_CAI_20260102160759.xlsx"
    )
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
        "acc.emolum.(stp.pen) - bon.da d/vision lab s.r.l. "
        "stipendio novembre 2025"
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
        "BONIFICO SEPA ISTANTANEO TRN CCTX00000263913948 BENEF. "
        "Lozza Lisa Ronzoni Mattia PER giroconto"
    )
    assert parsed.transactions[3].amount == Decimal("30.00")


def test_detect_signed_amount_xlsx_parser(tmp_path: Path) -> None:
    workbook_path = _build_signed_amount_xlsx(tmp_path)

    parser_name = detect_parser(workbook_path)

    assert parser_name == "signed_amount_xlsx"


def test_parse_signed_amount_xlsx_statement(tmp_path: Path) -> None:
    workbook_path = _build_signed_amount_xlsx(tmp_path)

    parsed = parse_statement(
        workbook_path,
        source_bank="Mattia",
    )

    assert parsed.parser_name == "signed_amount_xlsx"
    assert parsed.transactions[0].source_bank == "Mattia"
    assert parsed.transactions[0].amount == Decimal("-9.96")
    assert parsed.transactions[0].currency == "EUR"
    assert parsed.transactions[0].original_description == (
        "spesa con carta di credito nexi - sdd core: 8000640000050340681627 "
        "nexi payments s.p.a."
    )
    assert parsed.transactions[1].amount == Decimal("3689.00")


def _build_signed_amount_xlsx(tmp_path: Path) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "movimentiConto"
    worksheet.append(
        [
            "Data Contabile",
            "Data Valuta",
            "Importo",
            "Divisa",
            "Causale / Descrizione",
            "Stato ",
            "Canale",
        ]
    )
    worksheet.append(
        [
            "15/04/2026",
            "15/04/2026",
            -9.96,
            "EUR",
            "spesa con carta di credito nexi - sdd core: "
            "8000640000050340681627 "
            "nexi payments s.p.a.",
            "Cont.",
            "",
        ]
    )
    worksheet.append(
        [
            "01/04/2026",
            "01/04/2026",
            3689,
            "EUR",
            "BON.DA D/VISION LAB S.R.L. EMOLUMENTO MARZO 2026 NR. "
            "BONIFICO SEPA: "
            "PY0CSK54TETI RIF. BANCA ORDINANTE:  END TO END ID: ",
            "Cont.",
            "",
        ]
    )
    workbook_path = tmp_path / "movimentiContoMattia.xlsx"
    workbook.save(workbook_path)
    return workbook_path
