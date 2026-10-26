from fastapi.testclient import TestClient
from main import app
from database import get_connection
import pytest
pytestmark = pytest.mark.eval

client = TestClient(app)

def test_eval_retrieves_existing_appointment():
    response = client.post(
        "/chat",
        json={
            "message": "Hi, im Mike. What appointments do i have?"
        }
    )

    assert response.status_code == 200

    data = response.json()
    agent_response = data["response"]

    assert "Tire Change" in agent_response
    assert "11:00" in agent_response

def test_eval_understands_paraphrased_request():
        response = client.post(
            "/chat",
            json={
                "message": "Hey, Mike here — when am I bringing my car in?"
        }
        )

        assert response.status_code == 200

        data = response.json()
        agent_response = data["response"]

        assert "11:00" in agent_response

def test_eval_does_not_book_when_required_information_is_missing():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_before = cursor.fetchone()[0]

    connection.close()
    
    response = client.post(
        "/chat",
        json={
            "message": "Book me in for a tire change tomorrow."
        }
    )

    assert response.status_code == 200

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_after = cursor.fetchone()[0]

    connection.close()

    assert appointments_after == appointments_before

def test_eval_does_not_double_book_occupied_slot():
    response = client.post(
        "/chat",
        json={
            "message": (
                "Hi, I'm Mike. Please book a Brake Check "
                "on October 5, 2026 at 14:00."
            )
        }
    )

    assert response.status_code == 200

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

    booked_count = cursor.fetchone()[0]
    connection.close()

    assert booked_count == 1

def test_eval_can_reschedule_existing_appointment():
    response = client.post(
        "/chat",
        json={
            "message": (
                "Hi, I'm Mike. Move my Tire Change appointment "
                "to October 6, 2026 at 13:00."
            )
        }
    )

    assert response.status_code == 200

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT appointment_date, appointment_time
        FROM appointments
        WHERE customer_id = 1
        AND service_type = 'Tire Change'
        AND status = 'booked'
        """
    )

    appointment = cursor.fetchone()
    connection.close()

    assert appointment == ("2026-10-06", "13:00")