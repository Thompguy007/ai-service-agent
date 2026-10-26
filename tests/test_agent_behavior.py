from fastapi.testclient import TestClient
from main import app
from database import get_connection
import pytest

pytestmark = pytest.mark.eval

client = TestClient(app)

def test_chat_endpoint_works():
    response = client.post(
        "/chat",
        json={
            "message": "Hi, I'm Mike. What appointments do I have?"
}
    )


    assert response.status_code == 200

    data = response.json()

    assert "response" in data

    agent_response = data["response"]

    assert "Tire Change" in agent_response
    assert "11:00" in agent_response

def test_unknown_customer_does_not_get_fake_appointment():
    response = client.post(
        "/chat",
        json={
            "message": "Hi, I'm Batman. What appointments do I have?"
        }
    )

    assert response.status_code == 200

    data = response.json()
    agent_response = data["response"]

    print(agent_response)
    assert "Batman" in agent_response
    assert "Tire Change" not in agent_response
    assert "Oil Change" not in agent_response

def test_agent_handles_booked_slot_safely():
    response = client.post(
        "/chat",
        json={
            "message": "Hi, I'm Tom. Please book my BMW for a Brake Check on October 5, 2026 at 14:00."
        }
    )

    assert response.status_code == 200

    data = response.json()
    agent_response = data["response"]

    print(agent_response)

    assert "14:00" in agent_response
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
    """
    SELECT COUNT(*)
    FROM appointments
    WHERE appointment_date = ?
    AND appointment_time = ?
    AND status = 'booked'
    """,
    ("2026-10-05", "14:00")
)
    booking_count = cursor.fetchone()[0]
    connection.close()

    assert booking_count == 1
    