from fastapi.testclient import TestClient
from auth import create_access_token
from main import app
from database import get_connection
import pytest

pytestmark = pytest.mark.eval

client = TestClient(app)

def test_chat_endpoint_works(auth_headers):
    response = client.post(
    "/chat",
    json={
        "message": "Hi, I'm Mike. What appointments do I have?"
    },
    headers=auth_headers
)


    assert response.status_code == 200

    data = response.json()

    assert "response" in data

    agent_response = data["response"]

    assert "Tire Change" in agent_response or "Dækskift" in agent_response
    assert "11:00" in agent_response

def test_unknown_customer_does_not_get_fake_appointment(auth_headers):
    response = client.post(
        "/chat",
        json={
            "message": "Hi, I'm Batman. What appointments do I have?"
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    data = response.json()

    assert "response" in data

    agent_response = data["response"]

    print(f"\nAGENT RESPONSE:\n{agent_response}", flush=True)

    assert agent_response.strip(), "Agent returned an empty response"
    assert 'under the name "Batman"' not in agent_response
def test_agent_handles_booked_slot_safely():
    # Arrange: Reserve a future slot for Mike.
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
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
        (1, "2026-12-15", "14:00", "Oil Change", "booked")
    )

    connection.commit()
    connection.close()

    # Act: Tom attempts to book the same slot.
    token = create_access_token(customer_id=2)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": (
                "Hi, I'm Tom. Please book my BMW for a Brake Check "
                "on December 15, 2026 at 14:00."
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    # Assert: The AI must actually process the request.
    assert "temporarily unavailable" not in data["response"].lower()

    # Assert: The occupied slot must remain unchanged.
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT customer_id, service_type
        FROM appointments
        WHERE appointment_date = ?
        AND appointment_time = ?
        AND status = 'booked'
        """,
        ("2026-12-15", "14:00")
    )

    bookings = cursor.fetchall()
    connection.close()

    assert len(bookings) == 1
    assert bookings[0] == (1, "Oil Change")

    # Assert: The AI must check availability.
    assert "get_available_slots" in data["tools_used"]