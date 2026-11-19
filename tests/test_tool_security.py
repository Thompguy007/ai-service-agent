from unittest.mock import Mock, patch

from agent import execute_tool
from database import get_connection

def test_ai_cannot_override_authenticated_customer_id():
    mock_tool = Mock(return_value={"success": True})

    with patch.dict(
        "agent.TOOL_REGISTRY",
        {"cancel_appointment": mock_tool}
    ):
        result = execute_tool(
            tool_name="cancel_appointment",
            tool_input={
                "appointment_id": 2,
                "authenticated_customer_id": 999
            },
            authenticated_customer_id=1
        )

    mock_tool.assert_called_once_with(
        appointment_id=2,
        authenticated_customer_id=1
    )

    assert result == {"success": True}

from agent import execute_tool


def test_cannot_read_another_customers_appointments():
    # Customer 1 is authenticated
    authenticated_customer_id = 1

    # The AI attempts to retrieve customer 2's appointments
    result = execute_tool(
        tool_name="get_customer_appointments",
        tool_input={
            "customer_name": "Another Customer",
            "authenticated_customer_id": 2
        },
        authenticated_customer_id=authenticated_customer_id
    )

    # The tool must never return another customer's appointments
    if isinstance(result, list):
        assert all(
            appointment["customer_id"] == authenticated_customer_id
            for appointment in result
        )
    else:
        assert result["success"] is False

def test_ai_cannot_book_for_another_customer():
    result = execute_tool(
        tool_name="book_appointment",
        tool_input={
            "customer_id": 2,
            "appointment_date": "2027-06-15",
            "appointment_time": "10:00",
            "service_type": "Tire Change",
            "authenticated_customer_id": 2
        },
        authenticated_customer_id=1
    )

    assert result["success"] is False
    assert result["error"] == (
        "You cannot book appointments for another customer"
    )

def test_unauthorized_booking_does_not_modify_database():
    # Count appointments before the attack
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    before_count = cursor.fetchone()[0]

    connection.close()

    # Customer 1 attempts to book for customer 2
    result = execute_tool(
        tool_name="book_appointment",
        tool_input={
            "customer_id": 2,
            "appointment_date": "2027-06-15",
            "appointment_time": "10:00",
            "service_type": "Tire Change"
        },
        authenticated_customer_id=1
    )

    # Count appointments after the attack
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    after_count = cursor.fetchone()[0]

    connection.close()

    # Booking must be rejected
    assert result["success"] is False

    # Database must remain unchanged
    assert before_count == after_count


def test_authenticated_customer_can_book_appointment():
    customer_id = 1

    result = execute_tool(
        tool_name="book_appointment",
        tool_input={
            "customer_id": customer_id,
            "appointment_date": "2027-06-15",
            "appointment_time": "10:00",
            "service_type": "Tire Change"
        },
        authenticated_customer_id=customer_id
    )

    # Booking should succeed
    assert result["success"] is True
    assert result["customer_id"] == customer_id

    # Verify booking exists in database
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id, service_type, status
        FROM appointments
        WHERE id = ?
        """,
        (result["appointment_id"],)
    )

    appointment = cursor.fetchone()
    connection.close()

    assert appointment is not None
    assert appointment[0] == customer_id
    assert appointment[1] == "Tire Change"
    assert appointment[2] == "booked"

def test_booking_rejects_nonexistent_authenticated_customer():
    """Booking must reject authenticated customer IDs that do not exist."""

    from tools import book_appointment

    result = book_appointment(
        customer_id=99999,
        appointment_date="2027-06-16",
        appointment_time="10:00",
        service_type="Oil Change",
        authenticated_customer_id=99999
    )

    assert result["success"] is False

def test_ai_cannot_override_authenticated_customer_id():
    """AI tool arguments must not override the authenticated identity."""

    from agent import execute_tool
    from database import get_connection

    # Customer 2 attempts to impersonate customer 1
    result = execute_tool(
        tool_name="book_appointment",
        tool_input={
            "customer_id": 1,
            "authenticated_customer_id": 1,
            "appointment_date": "2027-07-15",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        },
        authenticated_customer_id=2
    )

    # Booking must be rejected
    assert result["success"] is False

    # Verify that no appointment was created
    connection = get_connection()

    try:
        appointment = connection.execute(
            """
            SELECT id
            FROM appointments
            WHERE appointment_date = ?
            AND appointment_time = ?
            """,
            ("2027-07-15", "10:00")
        ).fetchone()

    finally:
        connection.close()

    assert appointment is None

def test_ai_can_book_without_providing_customer_id():
    from agent import execute_tool
    from database import get_connection

    # Claude provides booking details but no customer ID
    result = execute_tool(
        tool_name="book_appointment",
        tool_input={
            "appointment_date": "2027-08-15",
            "appointment_time": "10:00",
            "service_type": "Tire Change"
        },
        authenticated_customer_id=1
    )

    # Booking must succeed
    assert result["success"] is True
    assert result["customer_id"] == 1

    # Verify that the appointment belongs to customer 1
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT customer_id
            FROM appointments
            WHERE id = ?
            """,
            (result["appointment_id"],)
        )

        appointment = cursor.fetchone()

        assert appointment is not None
        assert appointment[0] == 1

    finally:
        connection.close()