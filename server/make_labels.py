"""Generates labels.html: printable shelf labels with scannable UPC-A barcodes.

Some labels are deliberately wrong so the live demo produces real exceptions.
    python make_labels.py      -> writes labels.html next to this script
"""
import csv
import html
from pathlib import Path

L_CODES = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
R_CODES = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]

# barcode -> price printed on the shelf (cents). Anything not listed prints the correct system price.
WRONG_SHELF_PRICES = {
    "036000291452": 399,   # shelf higher than system: customer-trust issue, 4h SLA
    "073410013533": 999,   # shelf lower than system: revenue/compliance risk, 1h SLA
}


def upc_a_bits(code: str) -> str:
    if len(code) != 12 or not code.isdigit():
        raise ValueError(f"UPC-A needs 12 digits: {code}")
    left = "".join(L_CODES[int(d)] for d in code[:6])
    right = "".join(R_CODES[int(d)] for d in code[6:])
    return "101" + left + "01010" + right + "101"


def barcode_svg(code: str, module: float = 2.0, height: int = 70) -> str:
    bits = upc_a_bits(code)
    quiet = 9 * module
    width = len(bits) * module + 2 * quiet
    bars = "".join(
        f'<rect x="{quiet + i * module:.1f}" y="0" width="{module:.1f}" height="{height}"/>'
        for i, bit in enumerate(bits)
        if bit == "1"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height + 16}" '
        f'viewBox="0 0 {width:.0f} {height + 16}" role="img" aria-label="UPC {code}">'
        f'<rect width="100%" height="100%" fill="#fff"/><g fill="#000">{bars}</g>'
        f'<text x="{width / 2:.0f}" y="{height + 13}" font-family="monospace" font-size="12" '
        f'text-anchor="middle">{code}</text></svg>'
    )


def main() -> None:
    root = Path(__file__).resolve().parent
    rows = list(csv.DictReader((root / "data" / "price_master.csv").open(encoding="utf-8")))
    cards = []
    for row in rows:
        shelf = WRONG_SHELF_PRICES.get(row["barcode"], int(row["price_cents"]))
        dollars, cents = divmod(shelf, 100)
        cards.append(
            f"""<div class="label">
  <div class="name">{html.escape(row["description"])}</div>
  <div class="price">${dollars}.{cents:02d}</div>
  <div class="meta">Aisle {html.escape(row["aisle"])}</div>
  {barcode_svg(row["barcode"])}
</div>"""
        )
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ShelfSense demo labels</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; margin: 24px; background:#fff; color:#000; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:18px; }}
.label {{ border:2px solid #000; border-radius:6px; padding:12px 14px; background:#fffbe6; }}
.name {{ font-size:16px; font-weight:bold; }}
.price {{ font-size:54px; font-weight:900; line-height:1.1; margin:6px 0; }}
.meta {{ font-size:12px; margin-bottom:8px; }}
@media print {{ .label {{ break-inside: avoid; }} }}
</style></head><body><div class="grid">{''.join(cards)}</div></body></html>"""
    (root / "labels.html").write_text(page, encoding="utf-8")
    print(f"Wrote {root / 'labels.html'} with {len(cards)} labels")


if __name__ == "__main__":
    main()
