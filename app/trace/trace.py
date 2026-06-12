"""Trace helper utilities.

Every pipeline stage calls append_event() to push a TraceEvent onto the
shared ClaimTrace. The Trace Compiler (orchestrator) serialises the final
trace for the API response.

Design: ClaimTrace is passed by reference through the pipeline — each agent
receives it, appends its events, and returns. No global state is used.
"""

from datetime import datetime
from typing import Any, Literal

from app.schemas.trace import ClaimTrace, TraceEvent


def append_event(
    trace: ClaimTrace,
    *,
    stage: str,
    component: str,
    status: Literal["ok", "degraded", "failed"],
    summary: str,
    details: dict[str, Any] | None = None,
    timestamp: datetime | None = None,
) -> TraceEvent:
    """Create a TraceEvent and append it to *trace*.

    Args:
        trace:     The shared ClaimTrace being built for this claim.
        stage:     Pipeline stage name (e.g. "document_verification").
        component: Agent/function name (e.g. "DocumentVerificationAgent").
        status:    "ok", "degraded", or "failed".
        summary:   One-line human-readable summary — must be specific.
        details:   Structured payload (field_confidence map, check results, etc.).
        timestamp: Override timestamp (defaults to utcnow).

    Returns:
        The created TraceEvent (also appended to trace.events in-place).
    """
    event = TraceEvent(
        stage=stage,
        component=component,
        timestamp=timestamp or datetime.utcnow(),
        status=status,
        summary=summary,
        details=details or {},
    )
    trace.events.append(event)
    return event


def new_trace(claim_id: str) -> ClaimTrace:
    """Create a fresh ClaimTrace for a new claim processing run."""
    return ClaimTrace(claim_id=claim_id, events=[])
