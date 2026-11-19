from database import get_connection


def migrate():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'customers'
        """)

        result = cursor.fetchone()

        if result is None:
            raise RuntimeError("Customers table does not exist")

        if "'staff'" in result[0]:
            print("Staff role already supported.")
            return

        # Check existing database integrity
        if cursor.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Existing foreign key violations detected")

        # Rebuild the customers table safely.
        # Legacy alter-table behavior keeps appointments
        # referencing the final customers table name.
        # Disable foreign key enforcement before starting the transaction
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Start migration transaction
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            CREATE TABLE customers_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                vehicle TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'customer'
                    CHECK (role IN ('customer', 'staff', 'admin')),
                email TEXT,
                password_hash TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO customers_new
                (id, name, phone, vehicle, role, email, password_hash)
            SELECT
                id, name, phone, vehicle, role, email, password_hash
            FROM customers
        """)

        cursor.execute("DROP TABLE customers")

        cursor.execute("""
            ALTER TABLE customers_new
            RENAME TO customers
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX idx_unique_customer_email
            ON customers (email)
        """)

        # Verify that appointments still reference customers
        foreign_keys = cursor.execute(
            "PRAGMA foreign_key_list(appointments)"
        ).fetchall()

        if not any(row[2] == "customers" for row in foreign_keys):
            raise RuntimeError("Appointments foreign key was not preserved")

        violations = cursor.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign key violations after migration: {violations}"
            )

        connection.commit()

        print("Migration completed successfully.")
        print("Supported roles: customer, staff, admin")

    except Exception:
        connection.rollback()
        raise

    finally:
        # Ensure the transaction has ended before
        # restoring foreign key enforcement.
        if connection.in_transaction:
            connection.rollback()

        connection.execute("PRAGMA foreign_keys = ON")
        connection.close()


if __name__ == "__main__":
    migrate()