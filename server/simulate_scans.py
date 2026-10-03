"""Simulates a store walk: an associate scanning an aisle of shelf labels.

Usage (PowerShell):
    $env:SHELFSENSE_API_KEY = "your-key-here-min-16-chars"
    python simulate_scans.py --server http://127.0.0.1:8000
"""
import argparse
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx

WALK = [
    ("049000028911", 699, 0.97),   # match
    ("036000291452", 399, 0.94),   # shelf higher than system -> 4h fix
    ("073410013533", 999, 0.91),   # shelf lower than system -> 1h fix (revenue risk)
    ("078742370217", 389, 0.96),   # match
    ("021000658831", 129, 0.42),   # blurry -> recapture
    ("041220576463", 219, 0.71),   # looks like mismatch, actually an OCR misread (7 read as 1)
    ("999999999999", 250, 0.93),   # unknown SKU
    ("016000275287", 459, 0.95),   # match
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between scans")
    args = parser.parse_args()

    api_key = os.getenv("SHELFSENSE_API_KEY")
    if not api_key:
        print("Set SHELFSENSE_API_KEY first", file=sys.stderr)
        return 1

    with httpx.Client(base_url=args.server, headers={"X-Api-Key": api_key}, timeout=10) as client:
        for barcode, price, confidence in WALK:
            payload = {
                "scans": [
                    {
                        "client_id": str(uuid.uuid4()),
                        "device_id": "handheld-sim",
                        "store_id": "CHI-042",
                        "barcode": barcode,
                        "shelf_price_cents": price,
                        "ocr_raw_text": f"${price / 100:.2f}",
                        "ocr_confidence": confidence,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            }
            try:
                response = client.post("/api/v1/scans", json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                print(f"Server rejected scan: {error.response.status_code} {error.response.text}", file=sys.stderr)
                return 1
            except httpx.TransportError as error:
                print(f"Cannot reach server at {args.server}: {error}", file=sys.stderr)
                return 1
            result = response.json()["results"][0]
            print(f"{barcode}  shelf ${price / 100:>6.2f}  conf {confidence:.2f}  ->  {result['status']}")
            time.sleep(args.delay + random.uniform(0, 0.5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
