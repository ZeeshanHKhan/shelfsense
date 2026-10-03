import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from .llm import TaskWriter
from .models import (
    ExceptionOut,
    MetricsOut,
    ResolveIn,
    ScanBatchIn,
    ScanBatchOut,
    ScanResult,
    ScanStatus,
)
from .store import Product, ScanStore, classify, load_price_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("shelfsense")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DASHBOARD_HTML = (Path(__file__).resolve().parent / "dashboard.html").read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.getenv("SHELFSENSE_API_KEY")
    if not api_key or len(api_key) < 16:
        raise RuntimeError("Set SHELFSENSE_API_KEY (min 16 chars) before starting the server")
    app.state.api_key = api_key
    app.state.catalog = load_price_master(Path(os.getenv("SHELFSENSE_PRICE_MASTER", DATA_DIR / "price_master.csv")))
    app.state.store = ScanStore(os.getenv("SHELFSENSE_DB", "shelfsense.db"))
    app.state.tasks = TaskWriter(DATA_DIR / "sop.md")
    logger.info("Loaded %d SKUs from price master", len(app.state.catalog))
    yield
    app.state.tasks.close()
    app.state.store.close()


app = FastAPI(title="ShelfSense Edge Server", version="1.0.0", lifespan=lifespan)


def require_api_key(request: Request, x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key, request.app.state.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def _generate_task(app_: FastAPI, row_id: int, scan_status: ScanStatus, barcode: str,
                   product: Product | None, shelf_cents: int | None) -> None:
    task = app_.state.tasks.write(scan_status, barcode, product, shelf_cents)
    app_.state.store.set_task(row_id, task.text, task.source)


@app.post("/api/v1/scans", response_model=ScanBatchOut, dependencies=[Depends(require_api_key)])
def ingest_scans(batch: ScanBatchIn, background: BackgroundTasks, request: Request) -> ScanBatchOut:
    catalog: dict[str, Product] = request.app.state.catalog
    store: ScanStore = request.app.state.store
    results: list[ScanResult] = []
    for scan in batch.scans:
        product = catalog.get(scan.barcode)
        scan_status = classify(scan, product)
        expected = product.price_cents if product else None
        row_id, duplicate = store.insert_scan(scan, scan_status, expected)
        if not duplicate and scan_status != ScanStatus.MATCH:
            # The device never waits on the LLM: task text is generated after the response is sent.
            background.add_task(
                _generate_task, request.app, row_id, scan_status, scan.barcode, product, scan.shelf_price_cents
            )
        results.append(
            ScanResult(
                client_id=scan.client_id,
                status=scan_status,
                expected_price_cents=expected,
                description=product.description if product else None,
                duplicate=duplicate,
            )
        )
    return ScanBatchOut(results=results)


@app.get("/api/v1/exceptions", response_model=list[ExceptionOut], dependencies=[Depends(require_api_key)])
def list_exceptions(request: Request, store_id: str | None = None) -> list[ExceptionOut]:
    catalog: dict[str, Product] = request.app.state.catalog
    rows = request.app.state.store.open_exceptions(store_id)
    return [
        ExceptionOut(
            id=r["id"],
            store_id=r["store_id"],
            barcode=r["barcode"],
            description=catalog[r["barcode"]].description if r["barcode"] in catalog else None,
            aisle=catalog[r["barcode"]].aisle if r["barcode"] in catalog else None,
            status=ScanStatus(r["status"]),
            shelf_price_cents=r["shelf_price_cents"],
            expected_price_cents=r["expected_price_cents"],
            ocr_confidence=r["ocr_confidence"],
            task_text=r["task_text"],
            task_source=r["task_source"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


@app.post("/api/v1/exceptions/{exception_id}/resolve", status_code=204, dependencies=[Depends(require_api_key)])
def resolve_exception(exception_id: int, body: ResolveIn, request: Request) -> None:
    if not request.app.state.store.resolve(exception_id, body.resolution, body.corrected_price_cents):
        raise HTTPException(status_code=404, detail="Open exception not found")


@app.get("/api/v1/metrics", response_model=MetricsOut, dependencies=[Depends(require_api_key)])
def metrics(request: Request) -> MetricsOut:
    return MetricsOut(**request.app.state.store.metrics())


@app.get("/api/v1/feedback/ocr-misreads.jsonl", response_class=PlainTextResponse,
         dependencies=[Depends(require_api_key)])
def export_misreads(request: Request) -> str:
    return request.app.state.store.export_misreads_jsonl()


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML
