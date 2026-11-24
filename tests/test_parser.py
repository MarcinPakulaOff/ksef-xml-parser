from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ksef_xml import InvoiceError, parse_file, parse_invoice
from ksef_xml.cli import main
from ksef_xml.report import invoices_csv, lines_without_pkwiu, monthly_totals

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def inv():
    return parse_file(FIX / "sales.xml")


def test_header(inv):
    assert inv.number == "FV 1/10/2026"
    assert inv.issue_date == date(2026, 10, 27)
    assert inv.due_date == date(2026, 11, 10)
    assert inv.seller.nip == "1111111111"
    assert inv.buyer.nip == "2222222222"  # dashes stripped


def test_amounts_are_decimal_and_summed_across_rates(inv):
    assert inv.net == Decimal("1600.00")
    assert inv.vat == Decimal("350.00")
    assert inv.gross == Decimal("1950.00")
    assert isinstance(inv.net, Decimal)


def test_lines_accept_comma_decimals(inv):
    assert len(inv.lines) == 2
    assert inv.lines[1].unit_price == Decimal("50.00")
    assert inv.lines[0].pkwiu == "62.01.11.0"


def test_direction(inv):
    assert inv.direction("111-111-11-11") == "sales"
    assert inv.direction("2222222222") == "purchase"
    assert inv.direction("9999999999") == "other"


def test_monthly_totals_and_missing_pkwiu(inv):
    totals = monthly_totals([inv, inv], "1111111111")
    assert totals["2026-10"]["sales"].count == 2
    assert totals["2026-10"]["sales"].gross == Decimal("3900.00")
    assert lines_without_pkwiu([inv], "1111111111") == [("FV 1/10/2026", 2, "Printed booklet")]


def test_csv_has_header_and_row(inv):
    rows = invoices_csv([inv], "1111111111").splitlines()
    assert rows[0].startswith("number;kind;direction")
    assert "FV 1/10/2026;VAT;sales;2026-10-27" in rows[1]


@pytest.mark.parametrize("xml", [b"not xml", b"<Other/>", b"<Faktura><Fa/></Faktura>"])
def test_bad_input_raises(xml):
    with pytest.raises(InvoiceError):
        parse_invoice(xml)


def test_cli_csv_skips_broken_files(tmp_path, capsys):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "ok.xml").write_bytes((FIX / "sales.xml").read_bytes())
    (tmp_path / "in" / "bad.xml").write_text("garbage")
    out = tmp_path / "out.csv"
    assert main(["csv", str(tmp_path / "in"), "--nip", "1111111111", "--out", str(out)]) == 0
    assert out.read_text().count("\n") == 2
    assert "skipped" in capsys.readouterr().err


def test_pkwiu_read_from_line_name_when_field_missing():
    xml = (FIX / "sales.xml").read_text().replace(
        "<P_7>Printed booklet</P_7>", "<P_7>Hosting, PKWiU 63.11.12.0, 11.2026</P_7>")
    inv = parse_invoice(xml.encode())
    assert inv.lines[1].pkwiu == "63.11.12.0"
