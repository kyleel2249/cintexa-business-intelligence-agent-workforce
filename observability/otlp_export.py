"""Optional external telemetry export (G16, docs/GAP_REGISTER.md).

Previously "internal telemetry first" meant there was no path out of this
process at all — spans/metrics lived only in `TelemetryStore` (this
process's own DB). This adds a best-effort OTLP/HTTP JSON exporter using
`httpx` (already a dependency — no new SDK weight added) so spans can flow
to any real collector (Jaeger, Tempo, an OTel Collector, etc.) when one is
configured.

Design constraints:
- Fully optional: does nothing unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- Never blocks or raises into the caller — a slow/unreachable collector must
  never affect request latency or task execution. Runs in a background
  thread with a short timeout and a bounded queue; drops spans under
  sustained backpressure rather than growing unbounded.
- JSON body shaped after the OTLP JSON traces schema
  (resourceSpans/scopeSpans/spans) so it's usable by real collectors, but
  this is a lightweight hand-rolled encoder, not the official
  `opentelemetry-sdk` — treat it as best-effort compatibility, not strict
  OTLP conformance.
"""

from __future__ import annotations

import atexit
import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "cintexa-bi-workforce")


def _endpoint() -> Optional[str]:
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None


def _span_to_otlp(span: Dict[str, Any]) -> Dict[str, Any]:
    start_ns = int((span.get("start_time") or 0) * 1e9)
    end_ns = int((span.get("end_time") or span.get("start_time") or 0) * 1e9)
    attrs = span.get("attributes") or {}
    kv = [
        {"key": k, "value": {"stringValue": str(v)}}
        for k, v in attrs.items()
    ]
    for extra_key in ("organisation_id", "correlation_id", "workflow_id", "task_id", "agent_id"):
        val = span.get(extra_key)
        if val:
            kv.append({"key": extra_key, "value": {"stringValue": str(val)}})
    return {
        "traceId": (span.get("trace_id") or "").replace("-", "")[:32].zfill(32),
        "spanId": (span.get("span_id") or "").replace("-", "")[:16].zfill(16),
        "parentSpanId": (span.get("parent_span_id") or "").replace("-", "")[:16].zfill(16)
        if span.get("parent_span_id")
        else None,
        "name": f"{span.get('component', '')}.{span.get('operation', '')}",
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "status": {"code": 2 if span.get("status") == "ERROR" else 1},
        "attributes": kv,
    }


class OtlpExporter:
    """Background, fire-and-forget OTLP/HTTP JSON exporter."""

    def __init__(self, max_queue: int = 2000, flush_interval_sec: float = 2.0):
        self._q: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=max_queue)
        self._flush_interval = flush_interval_sec
        self._stop = threading.Event()
        self._dropped = 0
        self._thread: Optional[threading.Thread] = None

    def _ensure_started(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True, name="otlp-exporter")
            self._thread.start()
            atexit.register(self.shutdown)

    def export_span(self, span: Dict[str, Any]) -> None:
        if not _endpoint():
            return
        self._ensure_started()
        try:
            self._q.put_nowait(span)
        except queue.Full:
            self._dropped += 1
            if self._dropped % 500 == 1:
                logger.warning(
                    "OTLP exporter queue full; dropped %d spans so far. "
                    "Collector at %s may be slow/unreachable.",
                    self._dropped,
                    _endpoint(),
                )

    def _run(self) -> None:
        import httpx

        batch = []
        last_flush = time.time()
        while not self._stop.is_set():
            try:
                span = self._q.get(timeout=0.5)
                batch.append(span)
            except queue.Empty:
                pass
            if batch and (len(batch) >= 100 or time.time() - last_flush >= self._flush_interval):
                self._flush(httpx, batch)
                batch = []
                last_flush = time.time()
        if batch:
            self._flush(httpx, batch)

    def _flush(self, httpx_mod, batch) -> None:
        endpoint = _endpoint()
        if not endpoint:
            return
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": _SERVICE_NAME}}
                        ]
                    },
                    "scopeSpans": [
                        {"scope": {"name": "cintexa.observability.tracing"}, "spans": [_span_to_otlp(s) for s in batch]}
                    ],
                }
            ]
        }
        try:
            httpx_mod.post(endpoint, json=payload, timeout=5.0)
        except Exception as exc:  # never let export failures affect the app
            logger.debug("OTLP export failed (non-fatal): %s", exc)

    def shutdown(self) -> None:
        self._stop.set()


_exporter = OtlpExporter()


def export_span(span_dict: Dict[str, Any]) -> None:
    """Best-effort external export. No-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    try:
        _exporter.export_span(span_dict)
    except Exception:
        pass
