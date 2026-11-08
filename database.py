import sqlite3
import os

DB_NAME = os.getenv("DB_NAME", "service_agent.db")


def get_connection():
    db_name = os.getenv("DB_NAME", "service_agent.db")
    return sqlite3.connect(db_name)

def create_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            vehicle TEXT NOT NULL
        )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        service_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'booked',
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    )
""")
    cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_booked_slot
    ON appointments (appointment_date, appointment_time)
    WHERE status = 'booked'
""")
    # Add authentication columns to existing databases
    cursor.execute("PRAGMA table_info(customers)")
    columns = [column[1] for column in cursor.fetchall()]

    if "email" not in columns:
        cursor.execute("""
            ALTER TABLE customers
            ADD COLUMN email TEXT
        """)

    if "password_hash" not in columns:
        cursor.execute("""
            ALTER TABLE customers
            ADD COLUMN password_hash TEXT
        """)

    # Ensure email addresses are unique
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_customer_email
        ON customers (email)
    """)
    connection.commit()
    connection.close()