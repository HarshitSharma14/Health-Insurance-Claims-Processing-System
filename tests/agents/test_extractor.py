"""Unit tests for the Extraction Agent (Gemini backend).

All LLM calls are mocked via asyncio.to_thread -- no live API calls.

Coverage:
- Happy path: well-formed Gemini JSON response -> correct ExtractedDocumentData
- Partial/illegible: is_partial=True, low field_confidence -> passed through
- Malformed JSON (fails Pydantic validation) -> retry once, then degraded
- Exception on call -> retry once, then degraded (overall_confidence==0.0)
- force_failure=True -> degraded immediately, to_thread never called
- Date coercion: YYYY-MM-DD string -> date object
- Line-item coercion: list-of-dicts -> list[LineItem]
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.extractor import _degraded, _parse_response, run
from app.schemas.claim import ClaimCategory, DocumentType, UploadedDocument
from app.schemas.extraction import ExtractedDocumentData
from app.trace.trace import new_trace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JPEG_1PX = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"CF7F\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11"
    b"\x00\xff\xd9"
)


def _doc(file_id="F001"):
    return UploadedDocument(
        file_id=file_id, file_name="prescription.jpg",
        content_type="image/jpeg", file_bytes=JPEG_1PX,
        document_type=DocumentType.PRESCRIPTION,
    )


def _trace():
    return new_trace("test-claim")


HAPPY_PATH_RAW = {
    "document_type": "PRESCRIPTION",
    "patient_name": "Rajesh Kumar",
    "diagnosis": "Viral Fever",
    "treatment": None,
    "doctor_name": "Dr. Arun Sharma",
    "doctor_registration": "KA/45678/2015",
    "hospital_name": "City Clinic",
    "date": "2024-11-01",
    "line_items": [
        {"description": "Consultation Fee", "amount": 1000.0},
        {"description": "CBC Test", "amount": 300.0},
    ],
    "total": 1300.0,
    "tests_ordered": ["CBC", "Dengue NS1"],
    "field_confidence": {"patient_name": 0.95, "diagnosis": 0.90, "total": 0.98},
    "overall_confidence": 0.93,
    "is_partial": False,
    "extraction_notes": None,
}

PARTIAL_RAW = {
    "document_type": "HOSPITAL_BILL",
    "patient_name": "Rajesh Kumar",
    "diagnosis": None,
    "treatment": None,
    "doctor_name": None,
    "doctor_registration": None,
    "hospital_name": "City Clinic",
    "date": "2024-11-01",
    "line_items": [{"description": "Consultation", "amount": 1000.0}],
    "total": None,
    "tests_ordered": [],
    "field_confidence": {"total": 0.2, "hospital_name": 0.85},
    "overall_confidence": 0.4,
    "is_partial": True,
    "extraction_notes": "Amount illegible due to rubber stamp over total field.",
}


def _patch_thread(return_value=None, side_effect=None):
    """Patch asyncio.to_thread to return a fixed value or raise an exception."""
    if side_effect is not None:
        async def fake_thread(fn, *args, **kwargs):
            raise side_effect
    else:
        async def fake_thread(fn, *args, **kwargs):
            return return_value
    return patch("app.agents.extractor.asyncio.to_thread", side_effect=fake_thread)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_correct_document_type():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert result.document_type == DocumentType.PRESCRIPTION
    assert result.overall_confidence == pytest.approx(0.93)
    assert result.is_partial is False


@pytest.mark.asyncio
async def test_happy_path_patient_name_extracted():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert result.patient_name == "Rajesh Kumar"
    assert result.diagnosis == "Viral Fever"
    assert result.doctor_registration == "KA/45678/2015"


@pytest.mark.asyncio
async def test_happy_path_line_items_coerced():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert len(result.line_items) == 2
    assert result.line_items[0].description == "Consultation Fee"
    assert result.line_items[0].amount == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_happy_path_date_coerced_to_date_object():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert result.date == date(2024, 11, 1)


@pytest.mark.asyncio
async def test_happy_path_file_id_preserved():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        result = await run(_doc(file_id="F999"), ClaimCategory.CONSULTATION, _trace())
    assert result.file_id == "F999"


@pytest.mark.asyncio
async def test_happy_path_trace_event_written():
    with _patch_thread(return_value=dict(HAPPY_PATH_RAW)):
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace)
    events = [e for e in trace.events if e.stage == "extraction"]
    assert len(events) == 1
    assert events[0].status == "ok"


# ---------------------------------------------------------------------------
# Partial / illegible response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_response_passed_through():
    with _patch_thread(return_value=dict(PARTIAL_RAW)):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert result.is_partial is True
    assert result.overall_confidence == pytest.approx(0.4)
    assert result.extraction_notes is not None
    assert "stamp" in result.extraction_notes.lower() or "illegible" in result.extraction_notes.lower()


@pytest.mark.asyncio
async def test_partial_response_trace_event_is_degraded():
    with _patch_thread(return_value=dict(PARTIAL_RAW)):
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace)
    events = [e for e in trace.events if e.stage == "extraction"]
    assert events[0].status == "degraded"


# ---------------------------------------------------------------------------
# Malformed JSON (fails Pydantic validation) -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_response_retries_once():
    bad_raw = {"document_type": "NOT_VALID", "overall_confidence": "bad"}
    call_count = 0

    async def fake_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return bad_raw

    with patch("app.agents.extractor.asyncio.to_thread", side_effect=fake_thread):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert call_count == 2  # original + 1 retry


@pytest.mark.asyncio
async def test_malformed_response_degraded_result():
    bad_raw = {"document_type": "INVALID", "overall_confidence": "bad"}
    with _patch_thread(return_value=bad_raw):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert result.document_type == DocumentType.UNKNOWN
    assert "failed" in result.extraction_notes.lower()


# ---------------------------------------------------------------------------
# Exception on call -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_retries_once():
    call_count = 0

    async def fake_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("network error")

    with patch("app.agents.extractor.asyncio.to_thread", side_effect=fake_thread):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_exception_degraded_extraction_notes():
    with _patch_thread(side_effect=TimeoutError("timed out")):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
    assert "failed after retry" in result.extraction_notes.lower()


@pytest.mark.asyncio
async def test_exception_trace_event_is_degraded():
    with _patch_thread(side_effect=RuntimeError("boom")):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            trace = _trace()
            await run(_doc(), ClaimCategory.CONSULTATION, trace)
    events = [e for e in trace.events if e.stage == "extraction"]
    assert len(events) == 1
    assert events[0].status == "degraded"


# ---------------------------------------------------------------------------
# force_failure=True -> degraded immediately, to_thread never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_failure_returns_degraded():
    call_count = 0

    async def fake_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {}

    with patch("app.agents.extractor.asyncio.to_thread", side_effect=fake_thread):
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace(), force_failure=True)

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert "simulated component failure" in result.extraction_notes.lower()
    assert call_count == 0  # never called


@pytest.mark.asyncio
async def test_force_failure_trace_event_degraded():
    with patch("app.agents.extractor.asyncio.to_thread", new_callable=AsyncMock):
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace, force_failure=True)
    events = [e for e in trace.events if e.stage == "extraction"]
    assert len(events) == 1
    assert events[0].status == "degraded"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_file_bytes_returns_degraded():
    doc_no_bytes = UploadedDocument(
        file_id="F_EMPTY", file_name="empty.jpg",
        content_type="image/jpeg", file_bytes=None,
        document_type=DocumentType.PRESCRIPTION,
    )
    with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
        result = await run(doc_no_bytes, ClaimCategory.CONSULTATION, _trace())
    assert result.overall_confidence == 0.0
    assert result.is_partial is True


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    """First attempt raises, second returns good data -> success."""
    call_count = 0

    async def fake_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient error")
        return dict(HAPPY_PATH_RAW)

    with patch("app.agents.extractor.asyncio.to_thread", side_effect=fake_thread):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == pytest.approx(0.93)
    assert result.is_partial is False
    assert call_count == 2


@pytest.mark.asyncio
async def test_extraction_does_not_raise():
    """Agent must never raise — always returns ExtractedDocumentData."""
    async def boom(fn, *args, **kwargs):
        raise RuntimeError("unexpected crash")

    with patch("app.agents.extractor.asyncio.to_thread", side_effect=boom):
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            try:
                result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
                raised = False
            except Exception:
                raised = True

    assert not raised
    assert isinstance(result, ExtractedDocumentData)
