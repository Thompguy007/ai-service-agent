from rate_limiter import RateLimiter


def test_rate_limiter_blocks_after_ten_requests():
    limiter = RateLimiter(max_requests=10, window_seconds=60)

    for _ in range(10):
        assert limiter.allow_request(customer_id=1) is True

    assert limiter.allow_request(customer_id=1) is False

def test_rate_limiter_is_separate_for_each_customer():
    limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    # Customer 1 uses all 10 requests
    for _ in range(10):
        assert limiter.allow_request(customer_id=1) is True

    # Customer 1 is now blocked
    assert limiter.allow_request(customer_id=1) is False

    # Customer 2 should still be allowed
    assert limiter.allow_request(customer_id=2) is True

    # Customer 1 should remain blocked
    assert limiter.allow_request(customer_id=1) is False

from unittest.mock import patch


def test_rate_limiter_resets_after_time_window():
    limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    # Simulate time = 100 seconds
    with patch("rate_limiter.time.monotonic", return_value=100):

        # Customer uses all 10 requests
        for _ in range(10):
            assert limiter.allow_request(customer_id=1) is True

        # Customer is blocked
        assert limiter.allow_request(customer_id=1) is False

    # Simulate time = 161 seconds
    with patch("rate_limiter.time.monotonic", return_value=161):

        # Old requests have expired
        assert limiter.allow_request(customer_id=1) is True

from concurrent.futures import ThreadPoolExecutor


def test_rate_limiter_handles_concurrent_requests():
    limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    customer_id = 1

    # Simulate 20 concurrent requests
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(
            executor.map(
                limiter.allow_request,
                [customer_id] * 20
            )
        )

    # Exactly 10 requests should be allowed
    assert results.count(True) == 10

    # Exactly 10 requests should be rejected
    assert results.count(False) == 10

def test_rate_limiter_calculates_retry_after():
    limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    customer_id = 1

    # Simulate time = 100 seconds
    with patch("rate_limiter.time.monotonic", return_value=100):

        # Customer uses all 10 requests
        for _ in range(10):
            assert limiter.allow_request(customer_id) is True

        # Customer has reached the limit
        assert limiter.allow_request(customer_id) is False

        # Full waiting period
        assert limiter.get_retry_after(customer_id) == 60

    # Simulate time = 115 seconds
    with patch("rate_limiter.time.monotonic", return_value=115):

        # 45 seconds remaining
        assert limiter.get_retry_after(customer_id) == 45

    # Simulate time = 160 seconds
    with patch("rate_limiter.time.monotonic", return_value=160):

        # Waiting period has expired
        assert limiter.get_retry_after(customer_id) == 0

        # Customer can send messages again
        assert limiter.allow_request(customer_id) is True