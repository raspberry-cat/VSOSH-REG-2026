from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)
from pydantic import BaseModel, Field

from application.features import FeatureExtractor
from application.parsers import LogParser
from application.services import AnomalyService
from application.training import train_model
from infrastructure.logging import configure_logging
from infrastructure.registry import ModelRegistry
from infrastructure.settings import settings
from infrastructure.storage import Storage

logger = logging.getLogger(__name__)
_PROM_REGISTRY = CollectorRegistry()
_ENV_LABEL = settings.environment
_METRIC_TOTAL = Counter(
    "log_events_total",
    "Total ingested log events",
    ["environment"],
    registry=_PROM_REGISTRY,
)
_METRIC_ANOMALIES = Counter(
    "log_anomalies_total",
    "Detected anomalous log events",
    ["environment"],
    registry=_PROM_REGISTRY,
)
_METRIC_RATE = Gauge(
    "log_anomaly_rate",
    "Anomaly rate for ingested logs",
    ["environment"],
    registry=_PROM_REGISTRY,
)
_LAST_INGEST_TS = Gauge(
    "log_last_ingest_timestamp",
    "Unix timestamp of last ingest",
    ["environment"],
    registry=_PROM_REGISTRY,
)


def _build_service(storage: Storage, registry: ModelRegistry) -> AnomalyService:
    parser = LogParser()
    feature_extractor = FeatureExtractor()
    return AnomalyService(
        settings=settings,
        parser=parser,
        feature_extractor=feature_extractor,
        registry=registry,
        storage=storage,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    storage = Storage(settings.database_url)
    storage.init_db()
    registry = ModelRegistry(settings.artifact_dir)
    app.state.service = None
    app.state.model_loaded = False
    try:
        app.state.service = _build_service(storage, registry)
        app.state.model_loaded = True
    except FileNotFoundError as exc:
        if settings.auto_train_on_startup:
            bootstrap_path = Path(settings.bootstrap_log_path)
            if bootstrap_path.exists():
                parser = LogParser()
                feature_extractor = FeatureExtractor()
                lines = bootstrap_path.read_text(encoding="utf-8").splitlines()
                events = parser.parse_lines(lines, settings.bootstrap_log_format)
                train_model(events, settings.model_type, registry, feature_extractor)
                app.state.service = _build_service(storage, registry)
                app.state.model_loaded = True
                logger.info("model_bootstrapped", extra={"path": str(bootstrap_path)})
            else:
                logger.warning("bootstrap_path_missing", extra={"path": str(bootstrap_path)})
        if not app.state.model_loaded:
            logger.warning("model_not_loaded", extra={"error": str(exc)})
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.service = None
app.state.model_loaded = False


class IngestRequest(BaseModel):
    format: Literal["jsonl", "plain"] = "jsonl"
    lines: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    received: int
    anomalies: int
    model_version: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": bool(app.state.model_loaded),
        "environment": settings.environment,
    }


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    service: AnomalyService | None = app.state.service
    if service is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Train a model first.")
    try:
        results = service.ingest(request.lines, request.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    anomalies = sum(1 for result in results if result.is_anomaly)
    total = len(results)
    _METRIC_TOTAL.labels(_ENV_LABEL).inc(total)
    _METRIC_ANOMALIES.labels(_ENV_LABEL).inc(anomalies)
    _METRIC_RATE.labels(_ENV_LABEL).set(float(anomalies) / float(total) if total else 0.0)
    _LAST_INGEST_TS.labels(_ENV_LABEL).set(_utc_now_timestamp())
    return IngestResponse(
        received=len(results),
        anomalies=anomalies,
        model_version=service.metadata.get("version", "unknown"),
    )


@app.get("/anomalies")
def anomalies(
    limit: int = Query(default=50, ge=1, le=500),
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
) -> dict:
    service: AnomalyService | None = app.state.service
    if service is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Train a model first.")
    return {"items": service.get_anomalies(limit=limit, min_score=min_score)}


@app.get("/metrics")
def metrics() -> dict:
    service: AnomalyService | None = app.state.service
    if service is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Train a model first.")
    return service.get_metrics()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/metrics/prometheus")
def prometheus_metrics() -> Response:
    payload = generate_latest(_PROM_REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


def _utc_now_timestamp() -> float:
    return float(time.time())


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Nginx Log Anomaly Dashboard</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap');
    :root {
      --bg-1: #f6f2eb;
      --bg-2: #e1eef5;
      --ink: #0d2b45;
      --ink-muted: #3f5e74;
      --card: #ffffff;
      --accent: #f08a24;
      --accent-soft: #ffe2c6;
      --shadow: 0 18px 40px rgba(13, 43, 69, 0.18);
    }
    * { box-sizing: border-box; }
    body {
      font-family: "Space Grotesk", "IBM Plex Sans", sans-serif;
      background: radial-gradient(circle at 20% 20%, var(--bg-2), var(--bg-1));
      margin: 0;
      color: var(--ink);
      min-height: 100vh;
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: -20% -10% auto auto;
      width: 420px;
      height: 420px;
      background: radial-gradient(circle, rgba(240, 138, 36, 0.25), transparent 70%);
      pointer-events: none;
    }
    header {
      background: linear-gradient(120deg, #0d2b45, #123e60);
      color: #f7f2eb;
      padding: 28px 32px;
    }
    header h1 { margin: 0 0 6px; font-size: 28px; }
    header p { margin: 0; color: rgba(247, 242, 235, 0.7); }
    .container { padding: 24px 32px 40px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .card {
      background: var(--card);
      border-radius: 16px;
      padding: 18px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
      animation: floatIn 0.6s ease both;
    }
    .card:nth-child(2) { animation-delay: 0.05s; }
    .card:nth-child(3) { animation-delay: 0.1s; }
    .card:nth-child(4) { animation-delay: 0.15s; }
    .card h3 { margin-top: 0; font-size: 14px; letter-spacing: 0.04em; color: var(--ink-muted); text-transform: uppercase; }
    .metric { font-size: 30px; font-weight: 600; color: var(--ink); }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #e6edf3; font-size: 13px; color: var(--ink); }
    th { color: var(--ink-muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; background: var(--accent-soft); color: #8a2d0f; font-size: 11px; font-weight: 600; }
    @keyframes floatIn {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @media (max-width: 640px) {
      header { padding: 20px 20px; }
      .container { padding: 20px; }
      table { display: block; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Nginx Log Anomaly Dashboard</h1>
    <p>Live summary of nginx access anomalies</p>
  </header>
  <div class="container">
    <div class="grid">
      <div class="card">
        <h3>Total requests</h3>
        <div class="metric" id="total">-</div>
      </div>
      <div class="card">
        <h3>Anomalous requests</h3>
        <div class="metric" id="anomalies">-</div>
      </div>
      <div class="card">
        <h3>Anomaly rate</h3>
        <div class="metric" id="rate">-</div>
      </div>
      <div class="card">
        <h3>Last ingest</h3>
        <div class="metric" id="last">-</div>
      </div>
    </div>
    <div class="card" style="margin-top: 16px;">
      <h3>Latest anomalies</h3>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Host</th>
            <th>Status</th>
            <th>Method</th>
            <th>Path</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody id="anomaly-table"></tbody>
      </table>
    </div>
  </div>
  <script>
    async function loadMetrics() {
      const response = await fetch('/metrics');
      const metrics = await response.json();
      document.getElementById('total').textContent = metrics.total_events;
      document.getElementById('anomalies').textContent = metrics.anomalies;
      document.getElementById('rate').textContent = (metrics.anomaly_rate * 100).toFixed(1) + '%';
      document.getElementById('last').textContent = metrics.last_ingest || '-';
    }

    async function loadAnomalies() {
      const response = await fetch('/anomalies?limit=10');
      const data = await response.json();
      const rows = data.items.map(item => {
        return `<tr>
          <td>${item.timestamp}</td>
          <td>${item.host || item.service || '-'}</td>
          <td><span class="badge">${item.status ?? '-'}</span></td>
          <td>${item.method || '-'}</td>
          <td>${item.path || item.message || '-'}</td>
          <td>${item.anomaly_score.toFixed(2)}</td>
        </tr>`;
      });
      document.getElementById('anomaly-table').innerHTML = rows.join('');
    }

    loadMetrics();
    loadAnomalies();
    setInterval(() => { loadMetrics(); loadAnomalies(); }, 5000);
  </script>
</body>
</html>
"""
