import sqlite3
import tools
import pytest

def test_booking_does_not_misreport_foreign_key_error(monkeypatch):
    """Foreign key errors must not be reported as double bookings."""

    real_get_connection = tools.get_connection

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "INSERT INTO appointments" in sql:
                raise sqlite3.IntegrityError(
                    "FOREIGN KEY constraint failed"
                )
            return self.cursor.execute(sql, params)

        def fetchone(self):
            return self.cursor.fetchone()

    monkeypatch.setattr(
        tools,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    result = tools.book_appointment(
        customer_id=1,
        appointment_date="2026-12-15",
        appointment_time="09:00",
        service_type="Oil Change",
        authenticated_customer_id=1
    )

    assert result["success"] is False
    assert result["error"] == "Invalid customer reference"

def test_booking_closes_connection_on_database_error(monkeypatch):
    """Database connection must close after an unexpected SQL error."""

    real_get_connection = tools.get_connection
    connections = []

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False
            connections.append(self)

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            self.closed = True
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "INSERT INTO appointments" in sql:
                raise sqlite3.OperationalError(
                    "Simulated database failure"
                )

            return self.cursor.execute(sql, params)

        def fetchone(self):
            return self.cursor.fetchone()

    monkeypatch.setattr(
        tools,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    try:
        tools.book_appointment(
            customer_id=1,
            appointment_date="2026-12-15",
            appointment_time="09:00",
            service_type="Oil Change",
            authenticated_customer_id=1
        )
    except sqlite3.OperationalError:
        pass

    assert len(connections) == 2
    assert all(connection.closed for connection in connections)

def test_reschedule_closes_connection_on_database_error(monkeypatch):
    """Rescheduling must close the connection after a database error."""

    real_get_connection = tools.get_connection
    connections = []

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False
            connections.append(self)

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            self.closed = True
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "UPDATE appointments" in sql:
                raise sqlite3.OperationalError(
                    "Simulated reschedule database failure"
                )

            return self.cursor.execute(sql, params)

        def fetchone(self):
            return self.cursor.fetchone()

    monkeypatch.setattr(
        tools,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    try:
        tools.reschedule_appointment(
            appointment_id=1,
            new_date="2026-12-16",
            new_time="10:00",
            authenticated_customer_id=1
        )
    except sqlite3.OperationalError:
        pass

    assert len(connections) == 1
    assert all(connection.closed for connection in connections)

def test_cancel_closes_connection_on_database_error(monkeypatch):
    """Cancellation must close the connection after a database error."""

    real_get_connection = tools.get_connection
    connections = []

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False
            connections.append(self)

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            self.closed = True
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "UPDATE appointments" in sql:
                raise sqlite3.OperationalError(
                    "Simulated cancellation database failure"
                )

            return self.cursor.execute(sql, params)

        def fetchone(self):
            return self.cursor.fetchone()

    monkeypatch.setattr(
        tools,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    try:
        tools.cancel_appointment(
            appointment_id=1,
            authenticated_customer_id=1
        )
    except sqlite3.OperationalError:
        pass

    assert len(connections) == 1
    assert all(connection.closed for connection in connections)

def test_delete_customer_closes_connection_on_database_error(monkeypatch):
    """Customer deletion must close the connection after a database error."""

    import main

    real_get_connection = main.get_connection
    connections = []

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False
            connections.append(self)

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            self.closed = True
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "DELETE FROM customers" in sql:
                raise sqlite3.OperationalError(
                    "Simulated customer deletion database failure"
                )

            return self.cursor.execute(sql, params)

    monkeypatch.setattr(
        main,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    try:
        main.delete_customer(customer_id=1)
    except sqlite3.OperationalError:
        pass

    assert len(connections) == 1
    assert all(connection.closed for connection in connections)

def test_create_customer_closes_connection_on_database_error(monkeypatch):
    """Customer creation must close its connection after a database error."""

    import main

    real_get_connection = main.get_connection
    connections = []

    class ConnectionProxy:
        def __init__(self, connection):
            self.connection = connection
            self.closed = False
            connections.append(self)

        def cursor(self):
            return CursorProxy(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def rollback(self):
            return self.connection.rollback()

        def close(self):
            self.closed = True
            return self.connection.close()

    class CursorProxy:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, params=()):
            if "INSERT INTO customers" in sql:
                raise sqlite3.OperationalError(
                    "Simulated customer creation database failure"
                )

            return self.cursor.execute(sql, params)

    monkeypatch.setattr(
        main,
        "get_connection",
        lambda: ConnectionProxy(real_get_connection())
    )

    customer = main.Customer(
        name="Test Customer",
        phone="12345678",
        vehicle="BMW"
    )

    with pytest.raises(sqlite3.OperationalError):
        main.create_customer(
            customer=customer,
            authenticated_customer_id=1
        )

    assert len(connections) == 1
    assert all(connection.closed for connection in connections)
