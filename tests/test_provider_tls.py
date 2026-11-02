import ssl
import threading
import time

import pytest

from gamecua.provider import ProviderFailure, RetryPolicy, retryable, with_retries


def tls_error(reason, cls=ssl.SSLError):
    error = cls(1, "TLS request failed")
    error.reason = reason
    return error


@pytest.mark.parametrize(
    "error",
    [
        tls_error("CERTIFICATE_VERIFY_FAILED", ssl.SSLCertVerificationError),
        tls_error("SSLV3_ALERT_BAD_RECORD_MAC", ssl.SSLCertVerificationError),
        tls_error("WRONG_VERSION_NUMBER"),
        tls_error("DECRYPTION_FAILED_OR_BAD_RECORD_MAC"),
        ssl.SSLError(1, "SSLV3_ALERT_BAD_RECORD_MAC"),
        RuntimeError("SSLV3_ALERT_BAD_RECORD_MAC"),
    ],
)
def test_other_tls_failures_remain_fatal(error):
    events = []

    def attempt(timeout):
        raise error

    assert not retryable(error)
    with pytest.raises(ProviderFailure, match="Non-retryable"):
        with_retries(RetryPolicy(), events.append, threading.Event(), None, attempt)
    assert len(events) == 1
    assert events[0]["retryable"] is False


def test_peer_record_alert_retries_without_accepting_failed_response():
    events, timeouts = [], []
    error = tls_error("SSLV3_ALERT_BAD_RECORD_MAC")

    def attempt(timeout):
        timeouts.append(timeout)
        if len(timeouts) == 1:
            raise error
        return "verified response", {"requests": 1}, "pinned-model"

    deadline = time.monotonic() + 2
    result, stats = with_retries(
        RetryPolicy(initial_delay=0), events.append, threading.Event(), deadline, attempt
    )
    assert result == "verified response"
    assert stats["attempts"] == 2
    assert stats["returned_model"] == "pinned-model"
    assert 0 < timeouts[1] <= timeouts[0] <= 2
    assert [event["type"] for event in events] == [
        "provider_error",
        "provider_backoff",
        "provider_success",
    ]
    assert events[0]["tls_reason"] == "SSLV3_ALERT_BAD_RECORD_MAC"
    assert events[0]["retryable"] is True


@pytest.mark.parametrize("attempts,delay,expected", [(2, 0, 2), (12, 10, 1)])
def test_peer_record_alert_respects_attempt_and_original_deadline_limits(attempts, delay, expected):
    events, calls = [], []

    def attempt(timeout):
        calls.append(timeout)
        raise tls_error("SSLV3_ALERT_BAD_RECORD_MAC")

    with pytest.raises(ProviderFailure, match="retry budget exhausted"):
        with_retries(
            RetryPolicy(attempts=attempts, initial_delay=delay),
            events.append,
            threading.Event(),
            time.monotonic() + 1,
            attempt,
        )
    assert len(calls) == expected
    assert len([event for event in events if event["type"] == "provider_success"]) == 0
