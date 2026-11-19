from fastapi.testclient import TestClient
from main import app
from database import get_connection
from auth import create_access_token

client = TestClient(app)


def test_customers_endpoint_requires_authentication():
    response = client.get("/customers")

    assert response.status_code in (401, 403)


def test_appointments_endpoint_requires_authentication():
    response = client.get("/appointments")

    assert response.status_code in (401, 403)

def test_customer_can_only_see_own_information():
    """Authenticated customers must only see their own data."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.get(
        "/customers",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert "customers" in data

    customers = data["customers"]

    assert len(customers) == 1
    assert customers[0]["id"] == 1

def test_customer_can_only_see_own_appointments():
    """Customers must not see appointments belonging to others."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.get(
        "/appointments",
        headers=headers
    )

    assert response.status_code == 200

    data = response.json()

    assert "appointments" in data

    appointments = data["appointments"]

    # Mike must not see Tom's appointments
    assert all(
        appointment["customer_name"] == "Mike"
        for appointment in appointments
    )

    # Mike should still see his own appointment
    assert any(
        appointment["customer_name"] == "Mike"
        for appointment in appointments
    )

def test_create_customer_requires_authentication():
    response = client.post(
        "/customers",
        json={
            "name": "Unauthorized User",
            "phone": "12345678",
            "vehicle": "BMW"
        }
    )

    assert response.status_code in (401, 403)


def test_delete_customer_requires_authentication():
    response = client.delete("/customers/2")

    assert response.status_code in (401, 403)


def test_create_appointment_requires_authentication():
    response = client.post(
        "/appointments",
        json={
            "customer_id": 2,
            "appointment_date": "2026-12-10",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code in (401, 403)

def test_customer_cannot_delete_another_customer():
    """Customer 1 must not be able to delete customer 2."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.delete(
        "/customers/2",
        headers=headers
    )

    # Mike must not be allowed to delete Tom
    assert response.status_code == 403

    # Verify that Tom still exists
    from database import get_connection

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM customers WHERE id = ?",
        (2,)
    )

    customer = cursor.fetchone()
    connection.close()

    assert customer is not None

def test_customer_cannot_book_for_another_customer():
    """Customer 1 must not create appointments for customer 2."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 2,
            "appointment_date": "2026-12-15",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 403

    # Verify that no unauthorized appointment was created
    from database import get_connection

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM appointments
        WHERE customer_id = ?
        AND appointment_date = ?
        AND appointment_time = ?
        """,
        (2, "2026-12-15", "10:00")
    )

    count = cursor.fetchone()[0]
    connection.close()

    assert count == 0

def test_customer_can_book_own_appointment():
    """Authenticated customers can book their own appointments."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 1,
            "appointment_date": "2026-12-16",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 200

    # Verify that the appointment belongs to Mike
    from database import get_connection

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id, appointment_date, appointment_time
        FROM appointments
        WHERE customer_id = ?
        AND appointment_date = ?
        AND appointment_time = ?
        """,
        (1, "2026-12-16", "10:00")
    )

    appointment = cursor.fetchone()
    connection.close()

    assert appointment is not None
    assert appointment[0] == 1
    assert appointment[1] == "2026-12-16"
    assert appointment[2] == "10:00"

def test_api_rejects_booking_outside_business_hours():
    """API must reject appointments outside business hours."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 1,
            "appointment_date": "2026-12-17",
            "appointment_time": "23:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 400

    assert "08:00 and 16:00" in response.json()["detail"]

    # Verify that the invalid appointment was not saved
    from database import get_connection

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM appointments
        WHERE customer_id = ?
        AND appointment_date = ?
        AND appointment_time = ?
        """,
        (1, "2026-12-17", "23:00")
    )

    count = cursor.fetchone()[0]
    connection.close()

    assert count == 0

def test_api_rejects_double_booking():
    """API must reject an already booked time slot."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE status = 'booked'
        ORDER BY appointment_date, appointment_time
        LIMIT 1
    """)

    booked_slot = cursor.fetchone()
    connection.close()

    assert booked_slot is not None, "No booked appointments in test database"

    booked_date, booked_time = booked_slot

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 1,
            "appointment_date": booked_date,
            "appointment_time": booked_time,
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 400
    assert "already booked" in response.json()["detail"].lower()


def test_api_rejects_invalid_appointment_date():
    """API must reject invalid appointment dates."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 1,
            "appointment_date": "2026-13-45",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 400

    assert "Invalid appointment date" in response.json()["detail"]

    # Verify that the invalid booking was not saved
    from database import get_connection

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM appointments
        WHERE customer_id = ?
        AND appointment_date = ?
        """,
        (1, "2026-13-45")
    )

    count = cursor.fetchone()[0]
    connection.close()

    assert count == 0

def test_regular_customer_cannot_create_customers():
    """Regular customers must not access admin-only endpoints."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Unauthorized Customer",
            "phone": "12345678",
            "vehicle": "BMW"
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"

    # Verify that no customer was created
    from database import get_connection

    connection = get_connection()

    try:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM customers
            WHERE name = ?
            """,
            ("Unauthorized Customer",)
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 0

def test_admin_can_create_customer():
    """Administrators must be allowed to create customers."""

    from database import get_connection

    # Give Mike admin privileges in the isolated test database
    connection = get_connection()

    try:
        connection.execute(
            "UPDATE customers SET role = 'admin' WHERE id = ?",
            (1,)
        )
        connection.commit()
    finally:
        connection.close()

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "New Customer",
            "phone": "12345678",
            "vehicle": "Audi A4"
        }
    )

    assert response.status_code == 200

    # Verify that the customer was created
    connection = get_connection()

    try:
        customer = connection.execute(
            """
            SELECT name, role
            FROM customers
            WHERE name = ?
            """,
            ("New Customer",)
        ).fetchone()
    finally:
        connection.close()

    assert customer is not None
    assert customer[0] == "New Customer"
    assert customer[1] == "customer"

def test_admin_cannot_assign_admin_role_through_customer_creation():
    """
    Customer creation must not allow assigning admin privileges.
    """

    from database import get_connection

    # Make Mike an administrator in the isolated test database
    connection = get_connection()

    try:
        connection.execute(
            "UPDATE customers SET role = 'admin' WHERE id = ?",
            (1,)
        )
        connection.commit()
    finally:
        connection.close()

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/customers",
        headers=headers,
        json={
            "name": "Privilege Escalation Test",
            "phone": "12345678",
            "vehicle": "BMW",
            "role": "admin"
        }
    )

    # Reject attempts to assign roles through customer creation
    assert response.status_code == 422

    connection = get_connection()

    try:
        customer = connection.execute(
            """
            SELECT role
            FROM customers
            WHERE name = ?
            """,
            ("Privilege Escalation Test",)
        ).fetchone()
    finally:
        connection.close()

    # If the customer was created, it must not be an admin
    assert customer is None

def test_admin_can_view_all_customers():
    """Administrators must be able to view all customers."""

    from database import get_connection

    # Give Mike administrator privileges
    connection = get_connection()

    try:
        connection.execute(
            "UPDATE customers SET role = 'admin' WHERE id = ?",
            (1,)
        )
        connection.commit()
    finally:
        connection.close()

    # Create an access token for Mike
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Request all customers
    response = client.get(
        "/customers",
        headers=headers
    )

    assert response.status_code == 200

    customers = response.json()["customers"]

    customer_ids = [customer["id"] for customer in customers]

    # Administrator must see both Mike and Tom
    assert 1 in customer_ids
    assert 2 in customer_ids

def test_admin_can_view_all_appointments():
    """Administrators must be able to view all customer appointments."""

    from database import get_connection

    # Give Mike administrator privileges
    connection = get_connection()

    try:
        connection.execute(
            "UPDATE customers SET role = 'admin' WHERE id = ?",
            (1,)
        )
        connection.commit()
    finally:
        connection.close()

    # Authenticate as Mike
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Request appointments
    response = client.get(
        "/appointments",
        headers=headers
    )

    assert response.status_code == 200

    appointments = response.json()["appointments"]

    customer_names = [
        appointment["customer_name"]
        for appointment in appointments
    ]

    # Administrator must see appointments from both customers
    assert "Mike" in customer_names
    assert "Tom" in customer_names

def test_admin_can_book_for_another_customer():
    """Administrators must be able to book for other customers."""

    from database import get_connection

    # Give Mike administrator privileges
    connection = get_connection()

    try:
        connection.execute(
            "UPDATE customers SET role = 'admin' WHERE id = ?",
            (1,)
        )
        connection.commit()
    finally:
        connection.close()

    # Authenticate as Mike (admin)
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Admin books an appointment for Tom (customer 2)
    response = client.post(
        "/appointments",
        headers=headers,
        json={
            "customer_id": 2,
            "appointment_date": "2026-12-18",
            "appointment_time": "10:00",
            "service_type": "Oil Change"
        }
    )

    assert response.status_code == 200

    # Verify that the appointment belongs to Tom
    connection = get_connection()

    try:
        appointment = connection.execute(
            """
            SELECT customer_id
            FROM appointments
            WHERE appointment_date = ?
            AND appointment_time = ?
            """,
            ("2026-12-18", "10:00")
        ).fetchone()
    finally:
        connection.close()

    assert appointment is not None
    assert appointment[0] == 2

def test_chat_requires_authentication():
    """Chat endpoint must reject requests without authentication."""

    response = client.post(
        "/chat",
        json={
            "message": "Book an oil change tomorrow at 10:00"
        }
    )

    assert response.status_code == 401

def test_chat_rejects_invalid_token():
    """Chat endpoint must reject invalid JWT tokens."""

    headers = {
        "Authorization": "Bearer this.is.not.a.valid.jwt"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": "Show my appointments"
        }
    )

    assert response.status_code == 401

def test_regular_customer_cannot_access_claude_test():
    """Regular customers must not access the Claude test endpoint."""

    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.get(
        "/test-claude",
        headers=headers
    )

    assert response.status_code == 403

def test_claude_test_requires_authentication():
    """Unauthenticated users must not access the Claude test endpoint."""

    response = client.get("/test-claude")

    assert response.status_code in (401, 403)