"""Trace schemas — first-class observability artifact.

Matches ClaimTrace / TraceEvent in observability.md.

Every pipeline stage appends at least one TraceEvent, even on success.
The trace is append-only during pipeline execution and serialized in the
final API response for UI rendering.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """A single event produced by one pipeline stage or component.

    stage:     pipeline stage name — one of "document_verification",
               "extraction", "policy_evaluation", "decision"
    component: the specific agent/function that wrote this event
    status:    "ok" on success, "degraded" if the stage fell back to a
               partial/zero-confidence result, "failed" for unrecoverable errors
    summary:   one-line human-readable summary — MUST be specific (not generic)
    details:   stage-specific structured payload, e.g.:
               extraction → field_confidence map
               policy     → list of PolicyCheckResult dicts
               decision   → confidence factors dict
    """

    stage: str
    component: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["ok", "degraded", "failed"]
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class ClaimTrace(BaseModel):
    """Full audit trail for a single claim, assembled by the Trace Compiler.

    events is append-only — components push to it as they execute.
    final_decision_explanation is mandatory and must be specific enough that
    an ops person can reconstruct the decision reasoning from the trace alone,
    without access to source code.
    """

    claim_id: str
    events: list[TraceEvent] = Field(default_factory=list)
    final_decision_explanation: str = ""  # populated by Decision Agent
