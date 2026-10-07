import sqlite3

DB_NAME = "service_agent.db"


def get_connection():
    return sqlite3.connect(DB_NAME)

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

    connection.commit()
    connection.close()