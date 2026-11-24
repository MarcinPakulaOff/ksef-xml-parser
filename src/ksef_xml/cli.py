"""ksef-xml — command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .parser import InvoiceError, iter_files, parse_file
from .report import invoices_csv, lines_csv, lines_without_pkwiu, monthly_totals


def _load(paths: list[str]) -> tuple[list, list[str]]:
    invoices, errors = [], []
    for f in iter_files([Path(p) for p in paths]):
        try:
            invoices.append(parse_file(f))
        except InvoiceError as exc:
            errors.append(str(exc))
    return invoices, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ksef-xml", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("csv", "summary"):
        p = sub.add_parser(name)
        p.add_argument("paths", nargs="+", help="XML files or directories")
        p.add_argument("--nip", required=True, help="your own NIP (decides sales vs purchase)")
    sub.choices["csv"].add_argument("--out", type=Path, required=True)
    sub.choices["csv"].add_argument("--lines", type=Path, help="also write invoice lines here")
    sub.choices["summary"].add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    invoices, errors = _load(args.paths)
    for e in errors:
        print(f"skipped: {e}", file=sys.stderr)

    if args.cmd == "csv":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(invoices_csv(invoices, args.nip), encoding="utf-8")
        if args.lines:
            args.lines.write_text(lines_csv(invoices, args.nip), encoding="utf-8")
        print(f"{len(invoices)} invoices -> {args.out}")
        return 1 if errors and not invoices else 0

    totals = monthly_totals(invoices, args.nip)
    missing = lines_without_pkwiu(invoices, args.nip)
    if args.json:
        print(json.dumps({
            "months": {m: {d: {"count": t.count, "net": str(t.net), "vat": str(t.vat),
                               "gross": str(t.gross)} for d, t in v.items()}
                       for m, v in totals.items()},
            "sales_lines_without_pkwiu": len(missing),
            "errors": errors,
        }, ensure_ascii=False, indent=2))
    else:
        for month, by_dir in totals.items():
            for d, t in by_dir.items():
                print(f"{month} {d:<9} {t.count:>3} inv  net {t.net:>10}  vat {t.vat:>9}  gross {t.gross:>10}")
        for number, no, name in missing:
            print(f"no PKWiU: {number} line {no} ({name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
