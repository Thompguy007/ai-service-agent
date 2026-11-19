from main import get_available_slots, book_appointment, reschedule_appointment
import sqlite3
from database import get_connection
import pytest

def test_get_available_slots():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE status = 'booked'
        ORDER BY appointment_date, appointment_time
        LIMIT 1
    """)

    booked_slot = cursor.fetchone()
    connection.close()

    assert booked_slot is not None, "No booked appointments in test database"

    booked_date, booked_time = booked_slot

    result = get_available_slots(booked_date)

    assert booked_time not in result["available_slots"]

def test_free_slot_is_available():
    result = get_available_slots("2026-10-05")

    assert "13:00" in result["available_slots"]

    print("PASS: 13:00 is correctly available")

def test_double_booking_is_blocked():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE status = 'booked'
        ORDER BY appointment_date, appointment_time
        LIMIT 1
    """)

    booked_slot = cursor.fetchone()
    connection.close()

    assert booked_slot is not None, "No booked appointments in test database"

    booked_date, booked_time = booked_slot

    result = book_appointment(
        customer_id=1,
        appointment_date=booked_date,
        appointment_time=booked_time,
        service_type="Brake Check",
        authenticated_customer_id=1
    )

    assert result["success"] is False

def test_reschedule_to_booked_slot_is_blocked():
    result = reschedule_appointment(
        appointment_id=1,
        new_date="2026-10-05",
        new_time="14:00"
    )

    assert result["success"] is False

    print("PASS: reschedule to booked slot is correctly blocked")

def test_database_blocks_double_booking():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT appointment_date, appointment_time
            FROM appointments
            WHERE status = 'booked'
            ORDER BY appointment_date, appointment_time
            LIMIT 1
        """)

        booked_slot = cursor.fetchone()

        assert booked_slot is not None, "No booked appointments in test database"

        booked_date, booked_time = booked_slot

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO appointments (
                    customer_id,
                    appointment_date,
                    appointment_time,
                    service_type,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                1,
                booked_date,
                booked_time,
                "Brake Check",
                "booked"
            ))

    finally:
        connection.rollback()
        connection.close()

def test_booking_rejects_invalid_date():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-02-31",
        appointment_time="13:00",
        service_type="Oil Change",
        authenticated_customer_id=1
    )

    assert result["success"] is False
    assert result["error"] == "Invalid appointment date. Use YYYY-MM-DD."

def test_booking_rejects_invalid_time():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-10-25",
        appointment_time="27:83",
        service_type="Oil_Change",
        authenticated_customer_id=1
    )

    assert result["success"] is False
    assert result["error"] == "Invalid appointment time. Use HH:MM."

def test_booking_rejects_time_outside_allowed_slots():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-10-25",
        appointment_time="03:00",
        service_type="Oil Change",
        authenticated_customer_id=1
    )

    assert result["success"] is False
    assert result["error"] == (
        "Appointment time must be between 08:00 and 16:00 on the hour."
    )

def test_run_agent_passes_authenticated_identity_to_tools(monkeypatch):
    """Agent must pass backend-authenticated identity to tools."""

    from types import SimpleNamespace
    import agent

    captured = {}

    # Simulate Claude requesting a booking
    tool_use = SimpleNamespace(
        type="tool_use",
        id="tool_123",
        name="book_appointment",
        input={
            "customer_id": 1,
            "authenticated_customer_id": 1,
            "appointment_date": "2027-08-10",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    responses = iter([
        SimpleNamespace(
            stop_reason="tool_use",
            content=[tool_use]
        ),
        SimpleNamespace(
            stop_reason="end_turn",
            content=[
                SimpleNamespace(
                    type="text",
                    text="The booking request was rejected."
                )
            ]
        )
    ])

    def fake_claude_response(**kwargs):
        return next(responses)

    def fake_execute_tool(
        tool_name,
        tool_input,
        authenticated_customer_id=None
    ):
        captured["tool_name"] = tool_name
        captured["tool_input"] = tool_input
        captured["authenticated_customer_id"] = authenticated_customer_id

        return {
            "success": False,
            "error": "Unauthorized"
        }

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_claude_response
    )

    monkeypatch.setattr(
        agent,
        "execute_tool",
        fake_execute_tool
    )

    # Actual authenticated user is customer 2
    result = agent.run_agent(
        message="Book an appointment for customer 1",
        authenticated_customer_id=2
    )

    assert captured["tool_name"] == "book_appointment"

    # Identity must come from backend, not Claude
    assert captured["authenticated_customer_id"] == 2

    # Claude's input must not change backend identity
    assert captured["tool_input"]["authenticated_customer_id"] == 1

    assert result["response"] == "The booking request was rejected."

def test_agent_handles_claude_api_failure(monkeypatch):
    """Agent must handle AI provider failures gracefully."""

    import agent

    def fake_claude_failure(**kwargs):
        raise ConnectionError("Claude API unavailable")

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_claude_failure
    )

    result = agent.run_agent(
        message="Book an oil change tomorrow",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_claude_timeout(monkeypatch):
    """Agent must handle Anthropic API timeouts gracefully."""

    import httpx
    import agent
    from anthropic import APITimeoutError

    def fake_claude_timeout(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        raise APITimeoutError(request=request)

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_claude_timeout
    )

    result = agent.run_agent(
        message="Book an oil change tomorrow",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_anthropic_connection_error(monkeypatch):
    """Agent must handle Anthropic connection errors gracefully."""

    import httpx
    import agent
    from anthropic import APIConnectionError

    def fake_connection_error(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        raise APIConnectionError(request=request)

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_connection_error
    )

    result = agent.run_agent(
        message="Show my appointments",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_rate_limit_error(monkeypatch):
    """Agent must handle Anthropic rate limiting gracefully."""

    import httpx
    import agent
    from anthropic import RateLimitError

    def fake_rate_limit(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        response = httpx.Response(
            status_code=429,
            request=request,
            json={
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "Rate limit exceeded"
                }
            }
        )

        raise RateLimitError(
            message="Rate limit exceeded",
            response=response,
            body=response.json()
        )

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_rate_limit
    )

    result = agent.run_agent(
        message="Book an oil change tomorrow",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_internal_server_error(monkeypatch):
    """Agent must handle Anthropic server errors gracefully."""

    import httpx
    import agent
    from anthropic import InternalServerError

    def fake_server_error(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        response = httpx.Response(
            status_code=500,
            request=request,
            json={
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "Internal server error"
                }
            }
        )

        raise InternalServerError(
            message="Internal server error",
            response=response,
            body=response.json()
        )

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_server_error
    )

    result = agent.run_agent(
        message="Book an oil change tomorrow",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_anthropic_authentication_error(monkeypatch):
    """Agent must handle Anthropic authentication failures safely."""

    import httpx
    import agent
    from anthropic import AuthenticationError

    def fake_authentication_error(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        response = httpx.Response(
            status_code=401,
            request=request,
            json={
                "type": "error",
                "error": {
                    "type": "authentication_error",
                    "message": "Invalid API key"
                }
            }
        )

        raise AuthenticationError(
            message="Invalid API key",
            response=response,
            body=response.json()
        )

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_authentication_error
    )

    result = agent.run_agent(
        message="Show my appointments",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_anthropic_bad_request_error(monkeypatch):
    """Agent must handle invalid Anthropic API requests safely."""

    import httpx
    import agent
    from anthropic import BadRequestError

    def fake_bad_request(**kwargs):
        request = httpx.Request(
            "POST",
            "https://api.anthropic.com/v1/messages"
        )

        response = httpx.Response(
            status_code=400,
            request=request,
            json={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid request parameters"
                }
            }
        )

        raise BadRequestError(
            message="Invalid request parameters",
            response=response,
            body=response.json()
        )

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_bad_request
    )

    result = agent.run_agent(
        message="Book an oil change tomorrow",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "The assistant is temporarily unavailable. "
        "Please try again later."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []
