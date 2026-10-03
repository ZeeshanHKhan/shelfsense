from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ScanStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN_SKU = "UNKNOWN_SKU"
    NEEDS_RECAPTURE = "NEEDS_RECAPTURE"


class Resolution(str, Enum):
    LABEL_REPLACED = "LABEL_REPLACED"
    OCR_MISREAD = "OCR_MISREAD"


class ScanIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64, description="Device-generated UUID, used for idempotent retries")
    device_id: str = Field(min_length=1, max_length=64)
    store_id: str = Field(min_length=1, max_length=32)
    barcode: str = Field(pattern=r"^\d{8,14}$")
    shelf_price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    ocr_raw_text: str = Field(default="", max_length=500)
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    captured_at: datetime


class ScanBatchIn(BaseModel):
    scans: list[ScanIn] = Field(min_length=1, max_length=200)


class ScanResult(BaseModel):
    client_id: str
    status: ScanStatus
    expected_price_cents: int | None
    description: str | None
    duplicate: bool


class ScanBatchOut(BaseModel):
    results: list[ScanResult]


class ExceptionOut(BaseModel):
    id: int
    store_id: str
    barcode: str
    description: str | None
    aisle: str | None
    status: ScanStatus
    shelf_price_cents: int | None
    expected_price_cents: int | None
    ocr_confidence: float
    task_text: str | None
    task_source: str | None
    created_at: str


class ResolveIn(BaseModel):
    resolution: Resolution
    corrected_price_cents: int | None = Field(default=None, ge=0, le=10_000_000)


class MetricsOut(BaseModel):
    total_scans: int
    matches: int
    open_exceptions: int
    compliance_rate: float
    avg_ocr_confidence: float
    ocr_misreads_flagged: int
