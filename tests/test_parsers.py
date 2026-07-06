from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

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


def test_parse_structured_xlsx_with_truncated_dimension_ref(tmp_path: Path) -> None:
    workbook_path = _build_structured_xlsx_with_truncated_dimension(tmp_path)

    parsed = parse_statement(
        workbook_path,
        source_bank="Comune_ca",
    )

    assert parsed.parser_name == "structured_xlsx"
    assert len(parsed.transactions) == 10
    assert parsed.transactions[-1].original_description == "Movimento 10"
    assert all(
        not transaction.original_description.startswith("Totale")
        for transaction in parsed.transactions
    )


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


def _build_structured_xlsx_with_truncated_dimension(tmp_path: Path) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Lista Movimenti"
    worksheet.append(list(STRUCTURED_HEADER))
    for index in range(1, 11):
        worksheet.append(
            [
                f"{index:02d}/06/2026",
                f"{index:02d}/06/2026",
                "CAUSALE",
                f"Movimento {index}",
                str(index),
                "EUR",
            ]
        )
    worksheet.append([None, None, None, "Totale Entrate €", 55, None])
    worksheet.append([None, None, None, "Totale Uscite €", 55, None])

    workbook_path = tmp_path / "structured_truncated_dimension.xlsx"
    workbook.save(workbook_path)
    _rewrite_sheet_dimension_ref(workbook_path, "A1:F6")
    return workbook_path


def _rewrite_sheet_dimension_ref(workbook_path: Path, ref: str) -> None:
    entries: dict[str, bytes] = {}
    with ZipFile(workbook_path, "r") as archive:
        for member in archive.infolist():
            entries[member.filename] = archive.read(member.filename)

    sheet_xml_path = "xl/worksheets/sheet1.xml"
    root = ET.fromstring(entries[sheet_xml_path])
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    dimension = root.find("main:dimension", namespace)
    if dimension is None:
        raise AssertionError("Worksheet dimension tag is missing")
    dimension.set("ref", ref)
    entries[sheet_xml_path] = ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )

    with ZipFile(workbook_path, "w", compression=ZIP_DEFLATED) as archive:
        for member_name, payload in entries.items():
            archive.writestr(member_name, payload)


STRUCTURED_HEADER = (
    "Data Op.",
    "Data Val.",
    "Causale",
    "Descrizione",
    "Importo",
    "Div.",
)
