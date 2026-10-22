from main import get_available_slots, book_appointment, reschedule_appointment
import sqlite3

def test_get_available_slots():
    result = get_available_slots("2026-10-05")

    assert "14:00" not in result["available_slots"]

    print("PASS: 14:00 is correctly unavailable")

def test_free_slot_is_available():
    result = get_available_slots("2026-10-05")

    assert "13:00" in result["available_slots"]

    print("PASS: 13:00 is correctly available")

def test_double_booking_is_blocked():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-10-05",
        appointment_time="14:00",
        service_type="Brake Check"
    )

    assert result["success"] is False

    print("PASS: double booking is correctly blocked")

def test_reschedule_to_booked_slot_is_blocked():
    result = reschedule_appointment(
        appointment_id=1,
        new_date="2026-10-05",
        new_time="14:00"
    )

    assert result["success"] is False

    print("PASS: reschedule to booked slot is correctly blocked")

def test_database_blocks_double_booking():
    connection = sqlite3.connect("test_service_agent.db")
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO appointments (
                customer_id,
                appointment_date,
                appointment_time,
                service_type,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (1, "2026-10-05", "14:00", "Brake Check", "booked")
        )

        connection.commit()

        assert False, "Database allowed a double booking"

    except sqlite3.IntegrityError:
        pass

    finally:
        connection.close()

def test_booking_rejects_invalid_date():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-02-31",
        appointment_time="13:00",
        service_type="Oil Change"
    )

    assert result["success"] is False
    assert result["error"] == "Invalid appointment date. Use YYYY-MM-DD."

def test_booking_rejects_invalid_time():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-10-25",
        appointment_time="27:83",
        service_type="Oil_Change"
    )

    assert result["success"] is False
    assert result["error"] == "Invalid appointment time. Use HH:MM."

def test_booking_rejects_time_outside_allowed_slots():
    result = book_appointment(
        customer_id=1,
        appointment_date="2026-10-25",
        appointment_time="03:00",
        service_type="Oil Change"
    )

    assert result["success"] is False
    assert result["error"] == (
        "Appointment time must be between 08:00 and 16:00 on the hour."
    )