"""Unit tests for the Extraction Agent.

All LLM calls are mocked -- no live API calls.

Coverage:
- Happy path: well-formed tool_use response -> correct ExtractedDocumentData
- Partial/illegible: is_partial=True, low field_confidence -> passed through
- Malformed tool input (fails Pydantic validation) -> retry once, then degraded
- Timeout/APITimeoutError -> retry once, then degraded
- APIError -> retry once, then degraded
- No tool_use block (ValueError) -> retry once, then degraded
- force_failure=True -> degraded immediately, LLM client never called
- Date coercion: YYYY-MM-DD string -> date object
- Line-item coercion: list-of-dicts -> list[LineItem]
"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import anthropic
from app.agents.extractor import _degraded, _parse_tool_input, run
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
    b"\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t"
    b"\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
    b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A"
    b"\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1"
    b"\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJ"
    b"STUVWXYZcdefghijstuvwxyz\xff\xda\x00\x08\x01\x01\x00\x00?\x00"
    b"\xf5\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xd9"
)


def _doc(file_id="F001", content_type="image/jpeg"):
    return UploadedDocument(
        file_id=file_id,
        file_name="prescription.jpg",
        content_type=content_type,
        file_bytes=JPEG_1PX,
        document_type=DocumentType.PRESCRIPTION,
    )


def _trace():
    return new_trace("test-claim")


def _tool_use_block(input_dict: dict) -> MagicMock:
    """Build a mock ToolUseBlock."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_dict
    return block


def _mock_response(input_dict: dict) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [_tool_use_block(input_dict)]
    return resp


HAPPY_PATH_INPUT = {
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
    "field_confidence": {
        "patient_name": 0.95,
        "diagnosis": 0.90,
        "doctor_name": 0.92,
        "total": 0.98,
    },
    "overall_confidence": 0.93,
    "is_partial": False,
    "extraction_notes": None,
}

PARTIAL_INPUT = {
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
    "field_confidence": {
        "total": 0.2,
        "hospital_name": 0.85,
    },
    "overall_confidence": 0.4,
    "is_partial": True,
    "extraction_notes": "Amount illegible due to rubber stamp over total field.",
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_happy_path_returns_correct_document_type():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(return_value=_mock_response(HAPPY_PATH_INPUT))
        MockClient.return_value.messages.create = mock_create

        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.document_type == DocumentType.PRESCRIPTION
    assert result.overall_confidence == pytest.approx(0.93)
    assert result.is_partial is False


@pytest.mark.asyncio
async def test_happy_path_patient_name_extracted():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(HAPPY_PATH_INPUT)
        )
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.patient_name == "Rajesh Kumar"
    assert result.diagnosis == "Viral Fever"
    assert result.doctor_registration == "KA/45678/2015"


@pytest.mark.asyncio
async def test_happy_path_line_items_coerced():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(HAPPY_PATH_INPUT)
        )
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert len(result.line_items) == 2
    assert result.line_items[0].description == "Consultation Fee"
    assert result.line_items[0].amount == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_happy_path_date_coerced_to_date_object():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(HAPPY_PATH_INPUT)
        )
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.date == date(2024, 11, 1)


@pytest.mark.asyncio
async def test_happy_path_file_id_preserved():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(HAPPY_PATH_INPUT)
        )
        result = await run(_doc(file_id="F999"), ClaimCategory.CONSULTATION, _trace())

    assert result.file_id == "F999"


@pytest.mark.asyncio
async def test_happy_path_trace_event_written():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(HAPPY_PATH_INPUT)
        )
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace)

    extraction_events = [e for e in trace.events if e.stage == "extraction"]
    assert len(extraction_events) == 1
    assert extraction_events[0].status == "ok"


# ---------------------------------------------------------------------------
# Partial / illegible response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_response_passed_through():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(PARTIAL_INPUT)
        )
        result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.is_partial is True
    assert result.overall_confidence == pytest.approx(0.4)
    assert result.extraction_notes is not None
    assert "stamp" in result.extraction_notes.lower() or "illegible" in result.extraction_notes.lower()


@pytest.mark.asyncio
async def test_partial_response_trace_event_is_degraded():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(PARTIAL_INPUT)
        )
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace)

    extraction_events = [e for e in trace.events if e.stage == "extraction"]
    assert extraction_events[0].status == "degraded"


# ---------------------------------------------------------------------------
# Malformed / invalid tool input -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_tool_input_retries_once():
    """Schema validation failure on both attempts -> degraded after 2 total calls."""
    bad_input = {"document_type": "NOT_A_VALID_TYPE", "overall_confidence": "not_a_float"}

    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(return_value=_mock_response(bad_input))
        MockClient.return_value.messages.create = mock_create
        # Speed up backoff for tests
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert result.extraction_notes is not None
    # Should have been called twice (original + 1 retry)
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_malformed_tool_input_degraded_result():
    bad_input = {"document_type": "INVALID", "overall_confidence": "bad"}

    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            return_value=_mock_response(bad_input)
        )
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.document_type == DocumentType.UNKNOWN
    assert "failed" in result.extraction_notes.lower()


# ---------------------------------------------------------------------------
# Timeout -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_retries_once():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(
            side_effect=anthropic.APITimeoutError(request=MagicMock())
        )
        MockClient.return_value.messages.create = mock_create
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert mock_create.call_count == 2  # original + 1 retry


@pytest.mark.asyncio
async def test_timeout_degraded_extraction_notes():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=anthropic.APITimeoutError(request=MagicMock())
        )
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert "failed after retry" in result.extraction_notes.lower()


@pytest.mark.asyncio
async def test_timeout_trace_event_is_degraded():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=anthropic.APITimeoutError(request=MagicMock())
        )
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            trace = _trace()
            await run(_doc(), ClaimCategory.CONSULTATION, trace)

    extraction_events = [e for e in trace.events if e.stage == "extraction"]
    assert len(extraction_events) == 1
    assert extraction_events[0].status == "degraded"


# ---------------------------------------------------------------------------
# API error -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_error_retries_once():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(
            side_effect=anthropic.APIStatusError(
                "Internal server error",
                response=MagicMock(status_code=500),
                body={},
            )
        )
        MockClient.return_value.messages.create = mock_create
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_api_error_overall_confidence_zero():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=anthropic.InternalServerError(
                "error", response=MagicMock(status_code=500), body={}
            )
        )
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True


# ---------------------------------------------------------------------------
# No tool_use block -> retry once, then degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_tool_use_block_retries_once():
    """Response with no tool_use block raises ValueError -> retry -> degraded."""
    resp_no_tool = MagicMock()
    resp_no_tool.stop_reason = "end_turn"
    resp_no_tool.content = []  # no tool_use block

    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(return_value=resp_no_tool)
        MockClient.return_value.messages.create = mock_create
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert mock_create.call_count == 2


# ---------------------------------------------------------------------------
# force_failure=True -> degraded immediately, LLM client never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_failure_returns_degraded():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock()
        MockClient.return_value.messages.create = mock_create

        result = await run(
            _doc(), ClaimCategory.CONSULTATION, _trace(), force_failure=True
        )

    assert result.overall_confidence == 0.0
    assert result.is_partial is True
    assert "simulated component failure" in result.extraction_notes.lower()


@pytest.mark.asyncio
async def test_force_failure_llm_client_never_called():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock()
        MockClient.return_value.messages.create = mock_create

        await run(_doc(), ClaimCategory.CONSULTATION, _trace(), force_failure=True)

    # AsyncAnthropic was instantiated but messages.create must NOT have been called
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_force_failure_trace_event_degraded():
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock()
        trace = _trace()
        await run(_doc(), ClaimCategory.CONSULTATION, trace, force_failure=True)

    extraction_events = [e for e in trace.events if e.stage == "extraction"]
    assert len(extraction_events) == 1
    assert extraction_events[0].status == "degraded"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_file_bytes_returns_degraded():
    """Document with no file_bytes raises ValueError -> degraded."""
    doc_no_bytes = UploadedDocument(
        file_id="F_EMPTY",
        file_name="empty.jpg",
        content_type="image/jpeg",
        file_bytes=None,
        document_type=DocumentType.PRESCRIPTION,
    )
    with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
        result = await run(doc_no_bytes, ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == 0.0
    assert result.is_partial is True


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    """First attempt fails, second succeeds -> happy result returned."""
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        mock_create = AsyncMock(
            side_effect=[
                anthropic.APITimeoutError(request=MagicMock()),
                _mock_response(HAPPY_PATH_INPUT),
            ]
        )
        MockClient.return_value.messages.create = mock_create
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())

    assert result.overall_confidence == pytest.approx(0.93)
    assert result.is_partial is False
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_extraction_does_not_raise_on_any_failure():
    """The agent must never raise — always returns ExtractedDocumentData."""
    with patch("app.agents.extractor.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(
            side_effect=RuntimeError("completely unexpected crash")
        )
        with patch("app.agents.extractor.asyncio.sleep", new_callable=AsyncMock):
            try:
                result = await run(_doc(), ClaimCategory.CONSULTATION, _trace())
                raised = False
            except Exception:
                raised = True

    assert not raised
    assert isinstance(result, ExtractedDocumentData)
