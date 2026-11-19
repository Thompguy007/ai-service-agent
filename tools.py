from database import get_connection
import sqlite3
from datetime import datetime
from datetime import datetime
from zoneinfo import ZoneInfo

def is_valid_date(date_string: str):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_string: str):
    try:
        datetime.strptime(time_string, "%H:%M")
        return True
    except ValueError:
        return False

def is_allowed_booking_time(time_string: str):
    allowed_times = [
        "08:00",
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
        "16:00"
    ]

    return time_string in allowed_times

def get_available_slots(appointment_date: str):
    available_times = [
        "08:00",
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "13:00",
        "14:00",
        "15:00",
        "16:00"
    ]

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT appointment_time
            FROM appointments
            WHERE appointment_date = ?
            AND status = 'booked'
            """,
            (appointment_date,)
        )

        rows = cursor.fetchall()

    finally:
        connection.close()

    booked_times = [row[0] for row in rows]

    free_times = [
        time
        for time in available_times
        if time not in booked_times
    ]

    return {
        "date": appointment_date,
        "available_slots": free_times
    }

def get_customer_appointments(
    customer_name: str | None = None,
    authenticated_customer_id: int | None = None
):
    if authenticated_customer_id is None:
        return {
            "success": False,
            "error": "Authentication required"
        }

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                appointments.id,
                customers.id,
                customers.name,
                customers.vehicle,
                appointments.appointment_date,
                appointments.appointment_time,
                appointments.service_type,
                appointments.status
            FROM customers
            JOIN appointments
                ON customers.id = appointments.customer_id
            WHERE customers.id = ?
            ORDER BY
            appointments.appointment_date ASC,
            appointments.appointment_time ASC
            """,
            (authenticated_customer_id,)
        )

        rows = cursor.fetchall()

    finally:
        connection.close()

    appointments = []

    for row in rows:
        appointments.append({
            "appointment_id": row[0],
            "customer_id": row[1],
            "customer_name": row[2],
            "vehicle": row[3],
            "date": row[4],
            "time": row[5],
            "service_type": row[6],
            "status": row[7]
        })

    return appointments

def book_appointment(
    customer_id: int,
    appointment_date: str,
    appointment_time: str,
    service_type: str,
    authenticated_customer_id: int | None = None
):
    # Authentication required
    if authenticated_customer_id is None:
        return {
            "success": False,
            "error": "Authentication required"
        }

    # Verify authenticated customer and booking target
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Check authenticated customer
        cursor.execute(
            "SELECT role FROM customers WHERE id = ?",
            (authenticated_customer_id,)
        )

        authenticated_customer = cursor.fetchone()

        if authenticated_customer is None:
            return {
                "success": False,
                "error": "Authenticated customer does not exist"
            }

        # Check target customer
        cursor.execute(
            "SELECT id FROM customers WHERE id = ?",
            (customer_id,)
        )

        target_customer = cursor.fetchone()

        if target_customer is None:
            return {
                "success": False,
                "error": "Target customer does not exist"
            }

        # Check permissions
        if (
            customer_id != authenticated_customer_id
            and authenticated_customer[0] != "admin"
        ):
            return {
                "success": False,
                "error": "You cannot book appointments for another customer"
            }

    finally:
        connection.close()

    # Validate appointment date

    # Validate appointment date
    if not is_valid_date(appointment_date):
        return {
            "success": False,
            "error": "Invalid appointment date. Use YYYY-MM-DD."
        }

    # Validate appointment time
    if not is_valid_time(appointment_time):
        return {
            "success": False,
            "error": "Invalid appointment time. Use HH:MM."
        }

    # Validate business hours
    if not is_allowed_booking_time(appointment_time):
        return {
            "success": False,
            "error": "Appointment time must be between 08:00 and 16:00 on the hour."
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Check if the time slot is already booked
        cursor.execute(
            """
            SELECT id
            FROM appointments
            WHERE appointment_date = ?
            AND appointment_time = ?
            AND status = 'booked'
            """,
            (appointment_date, appointment_time)
        )

        existing_appointment = cursor.fetchone()

        if existing_appointment:
            return {
                "success": False,
                "error": "This time slot is already booked"
            }

        cursor.execute(
            """
            INSERT INTO appointments (
                customer_id,
                appointment_date,
                appointment_time,
                service_type
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                customer_id,
                appointment_date,
                appointment_time,
                service_type
            )
        )

        appointment_id = cursor.lastrowid
        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "customer_id": customer_id,
            "date": appointment_date,
            "time": appointment_time,
            "service_type": service_type,
            "status": "booked"
        }

    except sqlite3.IntegrityError as error:
        connection.rollback()

        error_message = str(error)

        if "UNIQUE constraint failed" in error_message:
            return {
                "success": False,
                "error": "This time slot is already booked"
            }

        if "FOREIGN KEY constraint failed" in error_message:
            return {
                "success": False,
                "error": "Invalid customer reference"
            }

        return {
            "success": False,
            "error": "Database integrity error"
        }

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def reschedule_appointment(
    appointment_id: int,
    new_date: str,
    new_time: str,
    authenticated_customer_id: int | None = None
):
    # Authentication required
    if authenticated_customer_id is None:
        return {
            "success": False,
            "error": "Authentication required"
        }

    # Validate date
    if not is_valid_date(new_date):
        return {
            "success": False,
            "error": "Invalid appointment date. Use YYYY-MM-DD."
        }

    # Validate time
    if not is_valid_time(new_time):
        return {
            "success": False,
            "error": "Invalid appointment time. Use HH:MM."
        }

    # Validate business hours
    if not is_allowed_booking_time(new_time):
        return {
            "success": False,
            "error": "Appointment time must be between 08:00 and 16:00 on the hour."
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Check whether the requested slot is occupied
        cursor.execute(
            """
            SELECT id
            FROM appointments
            WHERE appointment_date = ?
            AND appointment_time = ?
            AND status = 'booked'
            AND id != ?
            """,
            (new_date, new_time, appointment_id)
        )

        existing_appointment = cursor.fetchone()

        if existing_appointment:
            return {
                "success": False,
                "error": "The requested time slot is already booked"
            }

        # Update appointment
        cursor.execute(
            """
            UPDATE appointments
            SET appointment_date = ?,
                appointment_time = ?
            WHERE id = ?
            AND customer_id = ?
            AND status = 'booked'
            """,
            (
                new_date,
                new_time,
                appointment_id,
                authenticated_customer_id
            )
        )

        updated_rows = cursor.rowcount

        if updated_rows == 0:
            return {
                "success": False,
                "error": "Appointment not found or is not currently booked"
            }

        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "new_date": new_date,
            "new_time": new_time
        }

    except sqlite3.IntegrityError as error:
        connection.rollback()

        if "UNIQUE constraint failed" in str(error):
            return {
                "success": False,
                "error": "The requested time slot is already booked"
            }

        return {
            "success": False,
            "error": "Database integrity error"
        }

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def cancel_appointment(
    appointment_id: int,
    authenticated_customer_id: int | None = None
):
    # Authentication required
    if authenticated_customer_id is None:
        return {
            "success": False,
            "error": "Authentication required"
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Find appointment belonging to authenticated customer
        cursor.execute(
            """
            SELECT id, status
            FROM appointments
            WHERE id = ?
            AND customer_id = ?
            """,
            (appointment_id, authenticated_customer_id)
        )

        appointment = cursor.fetchone()

        if appointment is None:
            return {
                "success": False,
                "error": "Appointment not found"
            }

        if appointment[1] == "cancelled":
            return {
                "success": False,
                "error": "Appointment is already cancelled"
            }

        # Cancel appointment
        cursor.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE id = ?
            AND customer_id = ?
            AND status = 'booked'
            """,
            (appointment_id, authenticated_customer_id)
        )

        updated_rows = cursor.rowcount

        if updated_rows != 1:
            connection.rollback()

            return {
                "success": False,
                "error": "Appointment could not be cancelled"
            }

        connection.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "status": "cancelled"
        }

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_next_customer_appointment(
    authenticated_customer_id: int | None = None
):
    if authenticated_customer_id is None:
        return {
            "success": False,
            "error": "Authentication required"
        }

    appointments = get_customer_appointments(
        authenticated_customer_id=authenticated_customer_id
    )

    if isinstance(appointments, dict):
        return appointments

    now = datetime.now(ZoneInfo("Europe/Copenhagen"))

    upcoming = []

    for appointment in appointments:
        if appointment["status"] != "booked":
            continue

        appointment_datetime = datetime.strptime(
            f'{appointment["date"]} {appointment["time"]}',
            "%Y-%m-%d %H:%M"
        ).replace(tzinfo=ZoneInfo("Europe/Copenhagen"))

        if appointment_datetime > now:
            upcoming.append(appointment)

    if not upcoming:
        return {
            "success": True,
            "appointment": None
        }

    upcoming.sort(
        key=lambda appointment: (
            appointment["date"],
            appointment["time"]
        )
    )

    return {
        "success": True,
        "appointment": upcoming[0]
    }