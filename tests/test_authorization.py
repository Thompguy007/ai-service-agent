from database import get_connection
from tools import cancel_appointment
from tools import reschedule_appointment


def test_cancel_appointment_requires_authorization():
    # Tom owns appointment 2 in our seeded test database.
    # A cancellation without verified user identity must be rejected.

    result = cancel_appointment(2)

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT status FROM appointments WHERE id = ?",
        (2,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # The appointment must remain unchanged.
    assert appointment is not None
    assert appointment[0] == "booked"

    # The backend must reject an unauthenticated cancellation.
    assert result["success"] is False

def test_customer_cannot_cancel_another_customers_appointment():
    # Mike has customer_id = 1
    # Tom owns appointment_id = 2

    result = cancel_appointment(
        appointment_id=2,
        authenticated_customer_id=1
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT status FROM appointments WHERE id = ?",
        (2,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # Tom's appointment must remain booked
    assert appointment is not None
    assert appointment[0] == "booked"

    # Mike must not be allowed to cancel Tom's appointment
    assert result["success"] is False

def test_customer_can_cancel_own_appointment():
    # Mike owns appointment 1
    result = cancel_appointment(
        appointment_id=1,
        authenticated_customer_id=1
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT status FROM appointments WHERE id = ?",
        (1,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # Mike's appointment should now be cancelled
    assert appointment is not None
    assert appointment[0] == "cancelled"

    # The operation must report success
    assert result["success"] is True

def test_customer_cannot_reschedule_another_customers_appointment():
    # Mike (customer 1) attempts to reschedule Tom's appointment (ID 2)

    result = reschedule_appointment(
        appointment_id=2,
        new_date="2026-10-07",
        new_time="10:00"
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE id = ?
        """,
        (2,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # Tom's appointment must remain unchanged
    assert appointment == ("2026-10-05", "14:00")

    # Rescheduling without verified identity must be rejected
    assert result["success"] is False

def test_customer_cannot_reschedule_another_customers_appointment_with_identity():
    # Mike = customer 1
    # Tom owns appointment 2

    result = reschedule_appointment(
        appointment_id=2,
        new_date="2026-10-07",
        new_time="10:00",
        authenticated_customer_id=1
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE id = ?
        """,
        (2,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # Tom's appointment must remain unchanged
    assert appointment == ("2026-10-05", "14:00")

    # Mike must not be allowed to reschedule Tom's appointment
    assert result["success"] is False

def test_customer_can_reschedule_own_appointment():
    # Mike owns appointment 1
    result = reschedule_appointment(
        appointment_id=1,
        new_date="2026-10-07",
        new_time="10:00",
        authenticated_customer_id=1
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE id = ?
        """,
        (1,)
    )

    appointment = cursor.fetchone()
    connection.close()

    # Mike's appointment should have been rescheduled
    assert appointment == ("2026-10-07", "10:00")

    # The backend must confirm success
    assert result["success"] is True