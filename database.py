import sqlite3
import os

DB_NAME = os.getenv("DB_NAME", "service_agent.db")


def get_connection():
    db_name = os.getenv("DB_NAME", "service_agent.db")

    connection = sqlite3.connect(
        db_name,
        timeout=10
    )

    connection.execute("PRAGMA foreign_keys = ON")

    return connection

def create_database():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Create customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                vehicle TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer'
                    CHECK (role IN ('customer', 'staff', 'admin'))
            )
        """)

        # Create appointments table
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

        # Prevent double bookings
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_booked_slot
            ON appointments (appointment_date, appointment_time)
            WHERE status = 'booked'
        """)

        # Check existing customer columns
        cursor.execute("PRAGMA table_info(customers)")
        columns = [column[1] for column in cursor.fetchall()]

        # Add role column to existing databases
        if "role" not in columns:
            cursor.execute("""
                ALTER TABLE customers
                ADD COLUMN role TEXT NOT NULL DEFAULT 'customer'
                CHECK (role IN ('customer', 'staff', 'admin'))
            """)

        # Add email column
        if "email" not in columns:
            cursor.execute("""
                ALTER TABLE customers
                ADD COLUMN email TEXT
            """)

        # Add password hash column
        if "password_hash" not in columns:
            cursor.execute("""
                ALTER TABLE customers
                ADD COLUMN password_hash TEXT
            """)

        # Ensure unique email addresses
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_customer_email
            ON customers (email)
        """)

                # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE CASCADE
            )
        """)

        # Create conversation messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
            )
        """)

        # Optimize conversation lookups by customer
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_customer
            ON conversations(customer_id)
        """)

        # Optimize message retrieval by conversation
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON conversation_messages(conversation_id, id)
        """)

        # Save database changes
        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def create_conversation(customer_id: int) -> int:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO conversations (customer_id)
            VALUES (?)
            """,
            (customer_id,)
        )

        conversation_id = cursor.lastrowid

        connection.commit()

        return conversation_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()

def save_message(
    conversation_id: int,
    role: str,
    content: str
) -> int:

    if role not in ("user", "assistant"):
        raise ValueError("Invalid message role")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (conversation_id, role, content)
        )

        message_id = cursor.lastrowid

        connection.commit()

        return message_id

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_conversation_messages(
    conversation_id: int,
    customer_id: int
) -> list[dict]:

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                cm.role,
                cm.content
            FROM conversation_messages AS cm
            JOIN conversations AS c
                ON cm.conversation_id = c.id
            WHERE
                c.id = ?
                AND c.customer_id = ?
            ORDER BY cm.id ASC
            """,
            (conversation_id, customer_id)
        )

        rows = cursor.fetchall()

        return [
            {
                "role": row[0],
                "content": row[1]
            }
            for row in rows
        ]

    finally:
        connection.close()

def get_customer_conversations(customer_id: int) -> list[dict]:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                created_at
            FROM conversations
            WHERE customer_id = ?
            ORDER BY id DESC
            """,
            (customer_id,)
        )

        rows = cursor.fetchall()

        return [
            {
                "conversation_id": row[0],
                "created_at": row[1]
            }
            for row in rows
        ]

    finally:
        connection.close()

def conversation_belongs_to_customer(
    conversation_id: int,
    customer_id: int
) -> bool:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM conversations
            WHERE id = ?
              AND customer_id = ?
            """,
            (conversation_id, customer_id)
        )

        return cursor.fetchone() is not None

    finally:
        connection.close()

def save_message_pair(
    conversation_id: int,
    user_message: str,
    assistant_message: str
) -> None:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content
            )
            VALUES (?, 'user', ?)
            """,
            (conversation_id, user_message)
        )

        cursor.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content
            )
            VALUES (?, 'assistant', ?)
            """,
            (conversation_id, assistant_message)
        )

        connection.commit()

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()