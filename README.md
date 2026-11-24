# ksef-xml-parser

Parse Polish **KSeF e-invoices (FA(3) XML)** into typed Python records, then export **CSV** and **monthly totals**. Standard library only, no XML frameworks.

- Parties, dates, line items, VAT buckets and PKWiU codes (also read from the item name when the field is empty).
- Each invoice is classified as **sales or purchase** by comparing the seller NIP with your own.
- Lines without a PKWiU code are listed separately, because flat-rate tax (*ryczałt*) depends on it.
- Bad files do not stop the run: they are collected as errors and reported at the end.

It is the offline companion to [`ksef-api-client`](https://github.com/MarcinPakulaOff/ksef-api-client): that one downloads invoices from KSeF, this one turns a folder of XML files into a readable report.

## Usage

```bash
pip install -e .
ksef-xml csv ./invoices --nip 1111111111 --out invoices.csv --lines lines.csv
ksef-xml summary ./invoices --nip 1111111111          # monthly net / VAT / gross
ksef-xml summary ./invoices --nip 1111111111 --json
```

## Tests

```bash
pip install -e ".[dev]" && pytest -q
```

Tests run on a fictional invoice (`tests/fixtures/sales.xml`); CI runs them on Python 3.10 and 3.12.

## License

MIT
