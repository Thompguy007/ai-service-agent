
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from rate_limiter import RateLimiter


def test_login_rate_limit_blocks_sixth_attempt():
    client = TestClient(app)

    # Use an isolated limiter to avoid affecting other tests.
    test_limiter = RateLimiter(
        max_requests=5,
        window_seconds=300
    )

    with patch("main.login_rate_limiter", test_limiter):
        with patch("main.authenticate_customer", return_value=None) as mock_auth:

            # First five attempts should reach authentication.
            for attempt in range(5):
                response = client.post(
                    "/login",
                    json={
                        "email": "test@example.com",
                        "password": "wrong-password"
                    }
                )

                assert response.status_code == 401

            # Sixth attempt must be blocked before authentication.
            response = client.post(
                "/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong-password"
                }
            )

            assert response.status_code == 429
            assert "retry-after" in response.headers

            # Authentication should only run five times.
            assert mock_auth.call_count == 5


def test_login_rate_limit_isolated_by_ip():
    test_limiter = RateLimiter(
        max_requests=5,
        window_seconds=300
    )

    with patch("main.login_rate_limiter", test_limiter):
        with patch("main.authenticate_customer", return_value=None):
            client_a = TestClient(
                app,
                client=("192.0.2.10", 50000)
            )
            client_b = TestClient(
                app,
                client=("192.0.2.20", 50001)
            )

            # Client A uses all five attempts.
            for _ in range(5):
                response = client_a.post(
                    "/login",
                    json={
                        "email": "test@example.com",
                        "password": "wrong-password"
                    }
                )
                assert response.status_code == 401

            # Client A is now blocked.
            response = client_a.post(
                "/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong-password"
                }
            )
            assert response.status_code == 429

            # Client B must still be able to attempt login.
            response = client_b.post(
                "/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong-password"
                }
            )
            assert response.status_code == 401


def test_login_rate_limit_expires_after_five_minutes():
    client = TestClient(app)

    test_limiter = RateLimiter(
        max_requests=5,
        window_seconds=300
    )

    with patch("main.login_rate_limiter", test_limiter):
        with patch("main.authenticate_customer", return_value=None) as mock_auth:
            with patch("rate_limiter.time.monotonic") as mock_time:

                # Five attempts at the same simulated time.
                mock_time.return_value = 1000.0

                for _ in range(5):
                    response = client.post(
                        "/login",
                        json={
                            "email": "test@example.com",
                            "password": "wrong-password"
                        }
                    )
                    assert response.status_code == 401

                # Sixth attempt is blocked.
                response = client.post(
                    "/login",
                    json={
                        "email": "test@example.com",
                        "password": "wrong-password"
                    }
                )
                assert response.status_code == 429

                # Simulate 301 seconds passing.
                mock_time.return_value = 1301.0

                # Login attempts should be allowed again.
                response = client.post(
                    "/login",
                    json={
                        "email": "test@example.com",
                        "password": "wrong-password"
                    }
                )

                assert response.status_code == 401
                assert mock_auth.call_count == 6
