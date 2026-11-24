"""FA(3) e-invoice parser (Polish KSeF).

The schema namespace changes with every revision of the form, so elements are
matched by local name only. Amounts are Decimal, never float.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import xml.etree.ElementTree as ET

# Net (P_13_*) and VAT (P_14_*) fields of the FA(3) summary, one per tax rate.
NET_FIELDS = ["P_13_1", "P_13_2", "P_13_3", "P_13_4", "P_13_5", "P_13_6_1",
              "P_13_6_2", "P_13_6_3", "P_13_7", "P_13_8", "P_13_9", "P_13_10", "P_13_11"]
VAT_FIELDS = ["P_14_1", "P_14_2", "P_14_3", "P_14_4", "P_14_5"]
# Some invoicing apps put the code in the line description instead of the <PKWiU> field.
PKWIU_IN_TEXT = re.compile(r"PKWiU[:\s]*(\d{2}(?:\.\d{1,2}){1,3})", re.IGNORECASE)


class InvoiceError(ValueError):
    """The file is not a readable FA invoice."""


@dataclass(frozen=True)
class Party:
    nip: str
    name: str


@dataclass(frozen=True)
class Line:
    no: int
    name: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    net: Decimal
    vat_rate: str
    pkwiu: str


@dataclass(frozen=True)
class Invoice:
    number: str
    kind: str
    issue_date: date
    sale_date: date | None
    currency: str
    seller: Party
    buyer: Party
    net: Decimal
    vat: Decimal
    gross: Decimal
    due_date: date | None
    lines: list[Line] = field(default_factory=list)
    source: str = ""

    def direction(self, own_nip: str) -> str:
        """'sales' when `own_nip` issued the invoice, 'purchase' when it received it."""
        own = _digits(own_nip)
        if self.seller.nip == own:
            return "sales"
        if self.buyer.nip == own:
            return "purchase"
        return "other"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _find(node: ET.Element, *path: str) -> ET.Element | None:
    current: ET.Element | None = node
    for name in path:
        if current is None:
            return None
        current = next((c for c in current if _local(c.tag) == name), None)
    return current


def _text(node: ET.Element, *path: str, default: str = "") -> str:
    found = _find(node, *path)
    return (found.text or "").strip() if found is not None and found.text else default


def _amount(raw: str) -> Decimal:
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise InvoiceError(f"not an amount: {raw!r}") from exc


def _date(raw: str) -> date | None:
    return date.fromisoformat(raw[:10]) if raw else None


def _pkwiu(line: ET.Element) -> str:
    code = _text(line, "PKWiU")
    if code:
        return code
    match = PKWIU_IN_TEXT.search(_text(line, "P_7"))
    return match.group(1) if match else ""


def _party(root: ET.Element, tag: str) -> Party:
    node = _find(root, tag, "DaneIdentyfikacyjne")
    if node is None:
        return Party(nip="", name="")
    return Party(nip=_digits(_text(node, "NIP")), name=_text(node, "Nazwa"))


def parse_invoice(xml: str | bytes, source: str = "") -> Invoice:
    """Parse one FA invoice document."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise InvoiceError(f"{source or 'input'}: not XML ({exc})") from exc
    if _local(root.tag) != "Faktura":
        raise InvoiceError(f"{source or 'input'}: root is <{_local(root.tag)}>, expected <Faktura>")
    fa = _find(root, "Fa")
    if fa is None:
        raise InvoiceError(f"{source or 'input'}: no <Fa> section")

    issue = _date(_text(fa, "P_1"))
    if issue is None:
        raise InvoiceError(f"{source or 'input'}: no issue date (P_1)")

    lines = [
        Line(
            no=int(_text(w, "NrWierszaFa", default="0") or 0),
            name=_text(w, "P_7"),
            unit=_text(w, "P_8A"),
            quantity=_amount(_text(w, "P_8B")),
            unit_price=_amount(_text(w, "P_9A")),
            net=_amount(_text(w, "P_11")),
            vat_rate=_text(w, "P_12"),
            pkwiu=_pkwiu(w),
        )
        for w in fa
        if _local(w.tag) == "FaWiersz"
    ]

    return Invoice(
        number=_text(fa, "P_2"),
        kind=_text(fa, "RodzajFaktury", default="VAT"),
        issue_date=issue,
        sale_date=_date(_text(fa, "P_6")),
        currency=_text(fa, "KodWaluty", default="PLN"),
        seller=_party(root, "Podmiot1"),
        buyer=_party(root, "Podmiot2"),
        net=sum((_amount(_text(fa, f)) for f in NET_FIELDS), Decimal("0")),
        vat=sum((_amount(_text(fa, f)) for f in VAT_FIELDS), Decimal("0")),
        gross=_amount(_text(fa, "P_15")),
        due_date=_date(_text(fa, "Platnosc", "TerminPlatnosci", "Termin")),
        lines=lines,
        source=source,
    )


def parse_file(path: Path) -> Invoice:
    return parse_invoice(path.read_bytes(), source=str(path))


def iter_files(paths: list[Path]) -> list[Path]:
    """Expand directories into their *.xml files (recursively), sorted."""
    out: list[Path] = []
    for p in paths:
        out.extend(sorted(p.rglob("*.xml")) if p.is_dir() else [p])
    return out
