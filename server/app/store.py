import csv
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import Resolution, ScanIn, ScanStatus

LOW_CONFIDENCE_THRESHOLD = 0.60

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL UNIQUE,
    device_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    barcode TEXT NOT NULL,
    shelf_price_cents INTEGER,
    ocr_raw_text TEXT NOT NULL,
    ocr_confidence REAL NOT NULL,
    captured_at TEXT NOT NULL,
    status TEXT NOT NULL,
    expected_price_cents INTEGER,
    task_text TEXT,
    task_source TEXT,
    resolution TEXT,
    corrected_price_cents INTEGER,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_open ON scans(store_id, barcode, resolved_at);
"""


@dataclass(frozen=True)
class Product:
    barcode: str
    description: str
    price_cents: int
    aisle: str


def load_price_master(csv_path: Path) -> dict[str, Product]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return {
            row["barcode"]: Product(
                barcode=row["barcode"],
                description=row["description"],
                price_cents=int(row["price_cents"]),
                aisle=row["aisle"],
            )
            for row in csv.DictReader(handle)
        }


def classify(scan: ScanIn, product: Product | None) -> ScanStatus:
    if scan.ocr_confidence < LOW_CONFIDENCE_THRESHOLD or scan.shelf_price_cents is None:
        return ScanStatus.NEEDS_RECAPTURE
    if product is None:
        return ScanStatus.UNKNOWN_SKU
    if scan.shelf_price_cents != product.price_cents:
        return ScanStatus.MISMATCH
    return ScanStatus.MATCH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScanStore:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_scan(
        self, scan: ScanIn, status: ScanStatus, expected_price_cents: int | None
    ) -> tuple[int, bool]:
        """Returns (row_id, duplicate). Duplicate means the device retried a scan we already stored."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM scans WHERE client_id = ?", (scan.client_id,)
            ).fetchone()
            if existing is not None:
                return existing["id"], True
            cursor = self._conn.execute(
                """INSERT INTO scans (client_id, device_id, store_id, barcode, shelf_price_cents,
                   ocr_raw_text, ocr_confidence, captured_at, status, expected_price_cents, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    scan.client_id,
                    scan.device_id,
                    scan.store_id,
                    scan.barcode,
                    scan.shelf_price_cents,
                    scan.ocr_raw_text,
                    scan.ocr_confidence,
                    scan.captured_at.isoformat(),
                    status.value,
                    expected_price_cents,
                    _now(),
                ),
            )
            row_id = cursor.lastrowid
            if status == ScanStatus.MATCH:
                self._conn.execute(
                    """UPDATE scans SET resolution = ?, resolved_at = ?
                       WHERE store_id = ? AND barcode = ? AND status != ? AND resolved_at IS NULL""",
                    (
                        Resolution.LABEL_REPLACED.value,
                        _now(),
                        scan.store_id,
                        scan.barcode,
                        ScanStatus.MATCH.value,
                    ),
                )
            self._conn.commit()
            return row_id, False

    def set_task(self, row_id: int, task_text: str, task_source: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE scans SET task_text = ?, task_source = ? WHERE id = ?",
                (task_text, task_source, row_id),
            )
            self._conn.commit()

    def open_exceptions(self, store_id: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM scans WHERE status != ? AND resolved_at IS NULL"
        params: list[str] = [ScanStatus.MATCH.value]
        if store_id is not None:
            query += " AND store_id = ?"
            params.append(store_id)
        query += " ORDER BY id DESC"
        with self._lock:
            return self._conn.execute(query, params).fetchall()

    def get(self, row_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute("SELECT * FROM scans WHERE id = ?", (row_id,)).fetchone()

    def resolve(
        self, row_id: int, resolution: Resolution, corrected_price_cents: int | None
    ) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE scans SET resolution = ?, corrected_price_cents = ?, resolved_at = ?
                   WHERE id = ? AND status != ? AND resolved_at IS NULL""",
                (resolution.value, corrected_price_cents, _now(), row_id, ScanStatus.MATCH.value),
            )
            self._conn.commit()
            return cursor.rowcount == 1

    def metrics(self) -> dict[str, float | int]:
        with self._lock:
            row = self._conn.execute(
                """SELECT
                     COUNT(*) AS total,
                     COALESCE(SUM(CASE WHEN status = 'MATCH' THEN 1 ELSE 0 END), 0) AS matches,
                     COALESCE(SUM(CASE WHEN status != 'MATCH' AND resolved_at IS NULL THEN 1 ELSE 0 END), 0) AS open_ex,
                     COALESCE(AVG(ocr_confidence), 0) AS avg_conf,
                     COALESCE(SUM(CASE WHEN resolution = 'OCR_MISREAD' THEN 1 ELSE 0 END), 0) AS misreads
                   FROM scans"""
            ).fetchone()
        total = row["total"]
        return {
            "total_scans": total,
            "matches": row["matches"],
            "open_exceptions": row["open_ex"],
            "compliance_rate": round(row["matches"] / total, 4) if total else 0.0,
            "avg_ocr_confidence": round(row["avg_conf"], 4),
            "ocr_misreads_flagged": row["misreads"],
        }

    def export_misreads_jsonl(self) -> str:
        """Field-labeled OCR failures, shaped for the model team's retraining pipeline."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT barcode, ocr_raw_text, ocr_confidence, shelf_price_cents,
                          corrected_price_cents, device_id, store_id, captured_at
                   FROM scans WHERE resolution = 'OCR_MISREAD' ORDER BY id"""
            ).fetchall()
        return "".join(
            json.dumps(
                {
                    "barcode": r["barcode"],
                    "ocr_raw_text": r["ocr_raw_text"],
                    "ocr_confidence": r["ocr_confidence"],
                    "predicted_price_cents": r["shelf_price_cents"],
                    "label_price_cents": r["corrected_price_cents"],
                    "device_id": r["device_id"],
                    "store_id": r["store_id"],
                    "captured_at": r["captured_at"],
                }
            )
            + "\n"
            for r in rows
        )

    def close(self) -> None:
        self._conn.close()
