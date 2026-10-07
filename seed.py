from database import get_connection, create_database


def seed_database():
    create_database()

    connection = get_connection()
    cursor = connection.cursor()

    # Remove existing demo data
    cursor.execute("DELETE FROM appointments")
    cursor.execute("DELETE FROM customers")
    cursor.execute(
    "DELETE FROM sqlite_sequence WHERE name IN ('customers', 'appointments')"
)

    # Create demo customers
    customers = [
        ("Mike", "45453213", "Citroen Berlingo"),
        ("Tom", "12345678", "BMW")
    ]

    cursor.executemany(
        """
        INSERT INTO customers (name, phone, vehicle)
        VALUES (?, ?, ?)
        """,
        customers
    )

    # Get the generated customer IDs
    cursor.execute("SELECT id, name FROM customers")
    customer_rows = cursor.fetchall()

    customer_ids = {
        name: customer_id
        for customer_id, name in customer_rows
    }

    # Create demo appointments
    appointments = [
        (
            customer_ids["Mike"],
            "2026-10-02",
            "11:00",
            "Tire Change",
            "booked"
        ),
        (
            customer_ids["Tom"],
            "2026-10-05",
            "14:00",
            "Oil Change",
            "booked"
        )
    ]

    cursor.executemany(
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
        appointments
    )

    connection.commit()
    connection.close()
    print("Demo database seeded successfully.")


if __name__ == "__main__":
    seed_database()