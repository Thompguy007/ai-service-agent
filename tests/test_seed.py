from database import get_connection, create_database
from datetime import date, timedelta

def seed_test_database():
    create_database()

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM appointments")
        cursor.execute("DELETE FROM customers")

        customers = [
            (1, "Mike", "45453213", "Citroen Berlingo"),
            (2, "Tom", "12345678", "BMW")
        ]

        cursor.executemany(
            """
            INSERT INTO customers (id, name, phone, vehicle)
            VALUES (?, ?, ?, ?)
            """,
            customers
        )

       # Create future appointments so tests remain valid over time.
        today = date.today()

        mike_appointment = (today + timedelta(days=7)).isoformat()
        tom_appointment = (today + timedelta(days=10)).isoformat()

        appointments = [
            (1, 1, mike_appointment, "11:00", "Tire Change", "booked"),
            (2, 2, tom_appointment, "14:00", "Oil Change", "booked")
        ]

        cursor.executemany(
            """
            INSERT INTO appointments (
                id,
                customer_id,
                appointment_date,
                appointment_time,
                service_type,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            appointments
        )

        connection.commit()

    finally:
        connection.close()