import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from .models import ScanStatus
from .store import Product

logger = logging.getLogger("shelfsense.llm")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
LLM_ENABLED = os.getenv("SHELFSENSE_LLM_ENABLED", "true").lower() == "true"
LLM_TIMEOUT_SECONDS = float(os.getenv("SHELFSENSE_LLM_TIMEOUT", "30"))

PROMPT_TEMPLATE = """You are a store operations assistant writing a task for a frontline retail associate.
Use ONLY the SOP below. Write 2-3 short imperative sentences.
The price direction and deadline are already decided. Repeat that deadline exactly. Do not change it.
Do not tell the associate to set the item aside or notify a manager unless the status is UNKNOWN_SKU.
Do not invent policies. Do not use markdown.

SOP:
{sop}

Exception:
- Status: {status}
- Item: {description} (barcode {barcode}), aisle {aisle}
- Shelf label price: {shelf}
- System price: {expected}
- Decision: {direction}

Task for the associate:"""


@dataclass(frozen=True)
class TaskText:
    text: str
    source: str  # "llm:<model>" or "rules"


def _fmt(cents: int | None) -> str:
    return "unreadable" if cents is None else f"${cents / 100:.2f}"


def _direction(product: Product | None, shelf_cents: int | None) -> str:
    if product is None or shelf_cents is None or shelf_cents == product.price_cents:
        return "no price difference"
    if shelf_cents < product.price_cents:
        return "shelf price is LOWER than the system price. SOP deadline is 1 hour."
    return "shelf price is HIGHER than the system price. SOP deadline is 4 hours."


def rules_task(status: ScanStatus, barcode: str, product: Product | None, shelf_cents: int | None) -> str:
    if status == ScanStatus.NEEDS_RECAPTURE:
        return f"Rescan the shelf label for barcode {barcode}. The price could not be read reliably; hold the device steady and fill the frame with the label."
    if status == ScanStatus.UNKNOWN_SKU or product is None:
        return f"Barcode {barcode} is not in the system. Set the item aside and notify the department manager. Do not sell it until it is set up."
    if shelf_cents is not None and shelf_cents < product.price_cents:
        return (
            f"Replace the label for {product.description} in aisle {product.aisle} within 1 hour: "
            f"shelf shows {_fmt(shelf_cents)}, system price is {_fmt(product.price_cents)}. "
            "Reprint from the handheld and rescan to close."
        )
    return (
        f"Replace the label for {product.description} in aisle {product.aisle} within 4 hours: "
        f"shelf shows {_fmt(shelf_cents)}, system price is {_fmt(product.price_cents)}. "
        "Reprint from the handheld and rescan to close."
    )


class TaskWriter:
    def __init__(self, sop_path: Path, client: httpx.Client | None = None) -> None:
        self._sop = sop_path.read_text(encoding="utf-8")
        self._client = client or httpx.Client(base_url=OLLAMA_URL, timeout=LLM_TIMEOUT_SECONDS)

    def write(
        self, status: ScanStatus, barcode: str, product: Product | None, shelf_cents: int | None
    ) -> TaskText:
        fallback = TaskText(rules_task(status, barcode, product, shelf_cents), "rules")
        if not LLM_ENABLED or status in (ScanStatus.NEEDS_RECAPTURE, ScanStatus.UNKNOWN_SKU):
            return fallback
        prompt = PROMPT_TEMPLATE.format(
            sop=self._sop,
            status=status.value,
            description=product.description if product else "unknown",
            barcode=barcode,
            aisle=product.aisle if product else "unknown",
            shelf=_fmt(shelf_cents),
            expected=_fmt(product.price_cents if product else None),
            direction=_direction(product, shelf_cents),
        )
        try:
            response = self._client.post(
                "/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 120},
                },
            )
            response.raise_for_status()
            text = response.json().get("response", "").strip()
        except httpx.TimeoutException:
            logger.warning("Ollama timed out after %ss, using rules fallback", LLM_TIMEOUT_SECONDS)
            return fallback
        except httpx.HTTPError as error:
            logger.warning("Ollama unavailable (%s), using rules fallback", error)
            return fallback
        except ValueError as error:
            logger.warning("Ollama returned non-JSON (%s), using rules fallback", error)
            return fallback
        if not text:
            return fallback
        return TaskText(text, f"llm:{OLLAMA_MODEL}")

    def close(self) -> None:
        self._client.close()
