from database import get_connection
import sqlite3

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

def get_customer_appointments(customer_name: str):
    connection = get_connection()
    cursor = connection.cursor()

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
        WHERE LOWER(customers.name) = LOWER(?)
        """,
        (customer_name,)
    )

    rows = cursor.fetchall()
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
    service_type: str
):
    connection = get_connection()
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
        connection.close()

        return {
            "success": False,
            "error": "This time slot is already booked"
        }


    try:
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

        connection.commit()
        appointment_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        connection.close()

        return {
            "success": False,
            "error": "This time slot is already booked"
        }

    connection.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "customer_id": customer_id,
        "date": appointment_date,
        "time": appointment_time,
        "service_type": service_type,
        "status": "booked"
    }

def reschedule_appointment(
    appointment_id: int,
    new_date: str,
    new_time: str
):
    connection = get_connection()
    cursor = connection.cursor()

    # Check om det nye tidspunkt allerede er optaget

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
        connection.close()
        return {
            "success": False,
            "error": "The requested time slot is already booked"
        }

    try:
        cursor.execute(
            """
            UPDATE appointments
            SET appointment_date = ?,
                appointment_time = ?
            WHERE id = ?
            AND status = 'booked'
            """,
            (new_date, new_time, appointment_id)
        )

    except sqlite3.IntegrityError:
        connection.close()

        return {
            "success": False,
            "error": "The requested time slot is already booked"
        }

    connection.commit()
    if cursor.rowcount == 0:
        connection.close()

        return {
            "success": False,
            "error": "Appointment not found or is not currently booked"
        }

    connection.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "new_date": new_date,
        "new_time": new_time
    }
def cancel_appointment(appointment_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, status
        FROM appointments
        WHERE id = ?
        """,
        (appointment_id,)
    )

    appointment = cursor.fetchone()

    if appointment is None:
        connection.close()
        return {
            "success": False,
            "error": "Appointment not found"
        }

    if appointment[1] == "cancelled":
        connection.close()
        return {
            "success": False,
            "error": "Appointment is already cancelled"
        }

    cursor.execute(
        """
        UPDATE appointments
        SET status = 'cancelled'
        WHERE id = ?
        """,
        (appointment_id,)
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": "cancelled"
    }