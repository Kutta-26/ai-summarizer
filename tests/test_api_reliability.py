import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from main import app
from app.services.groq_service import (
    _call_groq_chat,
    _handle_groq_exception,
    _is_retryable_error,
    _get_retry_after,
    get_groq_client,
    close_groq_client
)
from groq import (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    InternalServerError,
    APIStatusError
)
import httpx

client = TestClient(app)


# ============================================================
# 1. SUCCESSFUL PROVIDER RESPONSE
# ============================================================

def test_successful_provider_response():
    """Verify standard successful Groq chat completion without retries."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="High-fidelity synthesized summary."))
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client):
        messages = [{"role": "system", "content": "You are a summarizer."}, {"role": "user", "content": "Sample text."}]
        result = _call_groq_chat(messages=messages, operation="summarization")
        assert result == "High-fidelity synthesized summary."
        assert mock_client.chat.completions.create.call_count == 1


# ============================================================
# 2. TEMPORARY NETWORK FAILURE & RETRY RECOVERY
# ============================================================

def test_temporary_network_failure_retries_and_succeeds():
    """Verify transient APIConnectionError is retried and recovers on next attempt."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Recovered after transient network drop."))
    ]

    mock_client = MagicMock()
    # First attempt raises connection drop, second attempt succeeds
    mock_client.chat.completions.create.side_effect = [
        APIConnectionError(request=MagicMock()),
        mock_response
    ]

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Network test."}]
        result = _call_groq_chat(messages=messages, operation="summarization")
        assert result == "Recovered after transient network drop."
        assert mock_client.chat.completions.create.call_count == 2
        assert mock_sleep.call_count == 1


# ============================================================
# 3. HTTP 429 RATE LIMIT WITH RETRY-AFTER
# ============================================================

def test_rate_limit_respects_retry_after():
    """Verify HTTP 429 inspects Retry-After header and applies bounded delay."""
    mock_response_success = MagicMock()
    mock_response_success.choices = [
        MagicMock(message=MagicMock(content="Summary after backoff."))
    ]

    # Create mock 429 with retry-after header
    mock_httpx_resp = MagicMock()
    mock_httpx_resp.status_code = 429
    mock_httpx_resp.headers = {"retry-after": "0.5"}

    rate_limit_err = RateLimitError(
        message="Rate limit exceeded",
        response=mock_httpx_resp,
        body=None
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        rate_limit_err,
        mock_response_success
    ]

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Rate limit test."}]
        result = _call_groq_chat(messages=messages, operation="summarization")
        assert result == "Summary after backoff."
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_with(0.5)


# ============================================================
# 4. HTTP 5XX TRANSIENT PROVIDER SERVER ERROR
# ============================================================

def test_transient_5xx_server_error_retries_and_succeeds():
    """Verify 502/503 provider errors are classified as retryable and succeed on retry."""
    mock_response_success = MagicMock()
    mock_response_success.choices = [
        MagicMock(message=MagicMock(content="Recovered after upstream 503."))
    ]

    mock_httpx_503 = MagicMock()
    mock_httpx_503.status_code = 503
    mock_httpx_503.headers = {}

    server_err = InternalServerError(
        message="Service Unavailable",
        response=mock_httpx_503,
        body=None
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        server_err,
        mock_response_success
    ]

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Server error test."}]
        result = _call_groq_chat(messages=messages, operation="summarization")
        assert result == "Recovered after upstream 503."
        assert mock_client.chat.completions.create.call_count == 2
        assert mock_sleep.call_count == 1


# ============================================================
# 5. PERMANENT 4XX FAILURES (NO RETRIES)
# ============================================================

def test_permanent_authentication_error_does_not_retry():
    """Verify HTTP 401 AuthenticationError fails immediately without retrying."""
    mock_httpx_401 = MagicMock()
    mock_httpx_401.status_code = 401
    mock_httpx_401.headers = {}

    auth_err = AuthenticationError(
        message="Invalid API Key",
        response=mock_httpx_401,
        body=None
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = auth_err

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Auth test."}]
        with pytest.raises(RuntimeError) as exc_info:
            _call_groq_chat(messages=messages, operation="summarization")

        assert "authentication failed" in str(exc_info.value).lower()
        # Verify call was attempted strictly once
        assert mock_client.chat.completions.create.call_count == 1
        assert mock_sleep.call_count == 0


def test_permanent_bad_request_does_not_retry():
    """Verify HTTP 400 BadRequestError fails immediately without wasting retry attempts."""
    mock_httpx_400 = MagicMock()
    mock_httpx_400.status_code = 400
    mock_httpx_400.headers = {}

    bad_req_err = BadRequestError(
        message="Invalid parameters",
        response=mock_httpx_400,
        body=None
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = bad_req_err

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Bad request test."}]
        with pytest.raises(RuntimeError) as exc_info:
            _call_groq_chat(messages=messages, operation="summarization")

        assert "rejected request parameters" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 1
        assert mock_sleep.call_count == 0


# ============================================================
# 6. TIMEOUT BEHAVIOR & RETRY EXHAUSTION
# ============================================================

def test_timeout_retries_and_exhausts():
    """Verify APITimeoutError retries up to max_attempts and exhausts with sanitized error."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Timeout test."}]
        with pytest.raises(RuntimeError) as exc_info:
            _call_groq_chat(messages=messages, operation="summarization")

        assert "timed out" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 3
        assert mock_sleep.call_count == 2


def test_rate_limit_exhaustion_raises_user_actionable_error():
    """Verify RateLimitError exhaustion returns expected user-facing error message."""
    mock_httpx_429 = MagicMock()
    mock_httpx_429.status_code = 429
    mock_httpx_429.headers = {}

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="Too many requests",
        response=mock_httpx_429,
        body=None
    )

    with patch("app.services.groq_service.get_groq_client", return_value=mock_client), \
         patch("time.sleep") as mock_sleep:
        messages = [{"role": "user", "content": "Rate limit exhaustion."}]
        with pytest.raises(RuntimeError) as exc_info:
            _call_groq_chat(messages=messages, operation="summarization")

        assert "Groq API rate limit reached during summarization" in str(exc_info.value)
        assert mock_client.chat.completions.create.call_count == 3
        assert mock_sleep.call_count == 2


# ============================================================
# 7. ERROR SANITIZATION & SECRET LEAK PREVENTION
# ============================================================

def test_sanitized_error_response_no_api_keys_leaked():
    """Verify that exceptions containing raw Groq API keys mask the key."""
    raw_leak_err = Exception("Failed connecting with key gsk_abc1234567890abcdef1234567890 to backend")
    sanitized = _handle_groq_exception(raw_leak_err, operation="summarization")
    sanitized_str = str(sanitized)

    assert "gsk_abc1234567890abcdef1234567890" not in sanitized_str
    assert "[REDACTED_API_KEY]" in sanitized_str


def test_context_length_exceeded_provides_hierarchical_guidance():
    """Verify context length exceeded error gives clear guidance to use hierarchical summarization."""
    mock_httpx_400 = MagicMock()
    mock_httpx_400.status_code = 400
    mock_httpx_400.headers = {}

    ctx_err = BadRequestError(
        message="Error code: 400 - {'error': {'message': 'context_length_exceeded: maximum context length is 8192 tokens'}}",
        response=mock_httpx_400,
        body=None
    )

    handled = _handle_groq_exception(ctx_err, operation="summarization")
    assert "hierarchical summarization" in str(handled).lower()


# ============================================================
# 8. OBSERVABILITY & REQUEST CORRELATION HEADERS
# ============================================================

def test_observability_x_request_id_and_process_time_headers():
    """Verify every HTTP response returns X-Process-Time and X-Request-ID correlation headers."""
    res = client.get("/health")
    assert res.status_code == 200
    assert "x-process-time" in res.headers
    assert res.headers["x-process-time"].endswith("s")
    assert "x-request-id" in res.headers
    assert len(res.headers["x-request-id"]) >= 6

    # Verify custom inbound X-Request-ID propagation
    custom_id = "test-corr-12345"
    res_custom = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res_custom.status_code == 200
    assert res_custom.headers.get("x-request-id") == custom_id
