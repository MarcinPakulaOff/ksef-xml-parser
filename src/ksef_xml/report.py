"""CSV export and monthly totals."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .parser import Invoice

INVOICE_COLUMNS = ["number", "kind", "direction", "issue_date", "sale_date", "due_date",
                   "currency", "seller_nip", "seller_name", "buyer_nip", "buyer_name",
                   "net", "vat", "gross", "source"]
LINE_COLUMNS = ["number", "direction", "issue_date", "line", "name", "pkwiu", "unit",
                "quantity", "unit_price", "net", "vat_rate"]


def invoices_csv(invoices: list[Invoice], own_nip: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(INVOICE_COLUMNS)
    for inv in invoices:
        w.writerow([inv.number, inv.kind, inv.direction(own_nip), inv.issue_date,
                    inv.sale_date or "", inv.due_date or "", inv.currency,
                    inv.seller.nip, inv.seller.name, inv.buyer.nip, inv.buyer.name,
                    inv.net, inv.vat, inv.gross, inv.source])
    return buf.getvalue()


def lines_csv(invoices: list[Invoice], own_nip: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(LINE_COLUMNS)
    for inv in invoices:
        for ln in inv.lines:
            w.writerow([inv.number, inv.direction(own_nip), inv.issue_date, ln.no, ln.name,
                        ln.pkwiu, ln.unit, ln.quantity, ln.unit_price, ln.net, ln.vat_rate])
    return buf.getvalue()


@dataclass
class Totals:
    count: int = 0
    net: Decimal = Decimal("0")
    vat: Decimal = Decimal("0")
    gross: Decimal = Decimal("0")


def monthly_totals(invoices: list[Invoice], own_nip: str) -> dict[str, dict[str, Totals]]:
    """{'2026-10': {'sales': Totals, 'purchase': Totals}} — PLN invoices only."""
    out: dict[str, dict[str, Totals]] = defaultdict(lambda: defaultdict(Totals))
    for inv in invoices:
        if inv.currency != "PLN":
            continue
        t = out[inv.issue_date.strftime("%Y-%m")][inv.direction(own_nip)]
        t.count += 1
        t.net += inv.net
        t.vat += inv.vat
        t.gross += inv.gross
    return {m: dict(v) for m, v in sorted(out.items())}


def lines_without_pkwiu(invoices: list[Invoice], own_nip: str) -> list[tuple[str, int, str]]:
    """Sales lines with no PKWiU code — a lump-sum (ryczałt) rate cannot be assigned to them."""
    return [(inv.number, ln.no, ln.name)
            for inv in invoices if inv.direction(own_nip) == "sales"
            for ln in inv.lines if not ln.pkwiu]
