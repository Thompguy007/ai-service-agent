from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token
from database import create_conversation, get_connection
from main import app

client = TestClient(app)
profile = {"name": "Demo Customer", "phone": "12345678", "vehicle": "Demo Car"}


@pytest.fixture
def headers():
    connection = get_connection()
    try:
        with connection:
            connection.executemany(
                "INSERT INTO customers (id, name, phone, vehicle, role) VALUES (?, ?, '', '', ?)",
                [(3, "Staff", "staff"), (4, "Admin", "admin")],
            )
    finally:
        connection.close()
    return {
        role: {"Authorization": f"Bearer {create_access_token(customer_id)}"}
        for role, customer_id in [("customer", 1), ("staff", 3), ("admin", 4)]
    }


def test_staff_can_book_reschedule_and_cancel_for_a_customer(headers):
    staff = headers["staff"]
    customer = headers["customer"]
    appointment_date = (date.today() + timedelta(days=21)).isoformat()
    booking = {
        "customer_id": 1,
        "appointment_date": appointment_date,
        "appointment_time": "10:00",
        "service_type": "Inspection",
    }
    assert len(client.get("/appointments", headers=staff).json()["appointments"]) == 2
    directory = client.get("/staff/customers", headers=staff)
    assert directory.status_code == 200
    assert directory.json()["customers"] == [{"id": 1, "name": "Mike"}, {"id": 2, "name": "Tom"}]
    assert client.post("/staff/appointments", headers=staff, json={**booking, "customer_id": 4}).status_code == 404
    response = client.post("/staff/appointments", headers=staff, json=booking)
    assert response.status_code == 201, response.json()
    path = f"/staff/appointments/{response.json()['appointment_id']}"
    update = {"new_date": appointment_date, "new_time": "12:00"}
    assert client.patch(path, headers=staff, json=update).status_code == 200
    appointments = client.get("/appointments", headers=customer).json()["appointments"]
    assert any(row["service_type"] == "Inspection" and row["time"] == "12:00" for row in appointments)
    assert client.post(f"{path}/cancel", headers=staff).status_code == 200
    assert client.post(f"{path}/cancel", headers=staff).status_code == 409
    appointments = client.get("/appointments", headers=customer).json()["appointments"]
    assert any(row["service_type"] == "Inspection" and row["status"] == "cancelled" for row in appointments)


def test_staff_booking_conflicts_and_missing_appointments(headers):
    staff = headers["staff"]
    appointments = client.get("/appointments", headers=staff).json()["appointments"]
    tom = next(row for row in appointments if row["customer_name"] == "Tom")
    payload = {"new_date": tom["date"], "new_time": tom["time"]}
    assert client.patch("/staff/appointments/1", headers=staff, json=payload).status_code == 409
    assert client.patch("/staff/appointments/999", headers=staff, json=payload).status_code == 404
    assert client.patch("/staff/appointments/1", headers=staff, json={**payload, "new_time": "10:30"}).status_code == 400
    assert client.patch("/staff/appointments/1", headers=staff, json={**payload, "new_date": "2030-1-1"}).status_code == 400
    assert client.post("/staff/appointments/1/cancel", headers=headers["admin"]).status_code == 200


@pytest.mark.parametrize(("method", "path", "payload"), [
    ("GET", "/staff/customers", None),
    ("POST", "/staff/appointments", {"customer_id": 1, "appointment_date": "2030-01-01",
                                    "appointment_time": "10:00", "service_type": "Inspection"}),
    ("PATCH", "/staff/appointments/1", {"new_date": "2030-01-01", "new_time": "10:00"}),
    ("POST", "/staff/appointments/1/cancel", None),
    ("PATCH", "/customers/2", profile),
    ("DELETE", "/admin/customers/2", None),
])
def test_customers_cannot_use_privileged_dashboard_endpoints(headers, method, path, payload):
    assert client.request(method, path, json=payload).status_code == 401
    assert client.request(method, path, headers=headers["customer"], json=payload).status_code == 403


def test_admin_manages_customer_login_and_profile(headers):
    admin = headers["admin"]
    staff = headers["staff"]
    login = {"email": "demo@example.com", "password": "local-demo-password"}
    assert client.post("/customers", headers=admin, json={**profile, "email": login["email"]}).status_code == 422
    invalid = client.post("/customers", headers=admin, json={**profile, "password": login["password"]})
    assert invalid.status_code == 422
    assert login["password"] not in invalid.text
    invalid = client.post("/customers", headers=admin, json={**profile, "email": login["email"], "password": "short12"})
    assert invalid.status_code == 422
    assert "short12" not in invalid.text
    response = client.post("/customers", headers=admin, json={**profile, **login})
    assert response.status_code == 200, response.json()
    assert login["password"] not in response.text
    customer_id = response.json()["customer_id"]
    path = f"/customers/{customer_id}"
    assert client.post("/customers", headers=admin, json={**profile, **login}).status_code == 409
    assert client.patch(path, headers=staff, json=profile).status_code == 403
    assert client.patch(path, headers=admin, json={**profile, "role": "admin"}).status_code == 422
    assert client.patch(path, headers=admin, json={**profile, "vehicle": "Updated Car"}).status_code == 200
    customers = client.get("/customers", headers=admin).json()["customers"]
    row = next(row for row in customers if row["id"] == customer_id)
    assert row["vehicle"] == "Updated Car"
    assert row["email"] == login["email"]
    assert row["role"] == "customer"
    assert "password_hash" not in row
    assert client.post("/login", json=login).status_code == 200
    assert client.delete(f"/admin/customers/{customer_id}", headers=admin).status_code == 204
    assert all(row["id"] != customer_id for row in client.get("/customers", headers=admin).json()["customers"])


def test_admin_deletion_preserves_bookings_conversations_and_privileged_accounts(headers):
    admin = headers["admin"]
    assert client.delete("/admin/customers/2", headers=admin).status_code == 409
    assert client.delete("/admin/customers/3", headers=admin).status_code == 404
    assert client.patch("/customers/3", headers=admin, json=profile).status_code == 404
    response = client.post("/customers", headers=admin, json=profile)
    customer_id = response.json()["customer_id"]
    create_conversation(customer_id)
    assert client.delete(f"/admin/customers/{customer_id}", headers=admin).status_code == 409
