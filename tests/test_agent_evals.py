from fastapi.testclient import TestClient
from main import app
from database import get_connection
import pytest
pytestmark = pytest.mark.eval
client = TestClient(app)

def test_database_isolation():
     import os
     db_name = os.getenv("DB_NAME")

     assert db_name is not None
     assert "test_service_agent.db" in db_name
     assert os.path.exists(db_name)

     connection = get_connection()

     cursor = connection.cursor()
     cursor.execute("PRAGMA database_list")

     database_path = cursor.fetchone()[2]

     connection.close()

     assert os.path.samefile(database_path, db_name)

       

# kan agenten finde en eksisterende aftale?
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
    assert "get_customer_appointments" in data["tools_used"]

# Forstå agenten forskellige formuleringer?
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

# Undgår agenten at booke uden nødvendige oplysninger? 
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

    # Inspect the agent's response and tool usage
    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    assert response.status_code == 200

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_after = cursor.fetchone()[0]

    connection.close()

    # Database kontrol: ingen ekstra aftaler må være oprettet.
    assert appointments_after == appointments_before

    # Agent kontrol: Agenten må ikke forsøge at anvende booking værktøjet,
    #  når nødvendige oplysninger mangler.
    assert "book_appointment" not in data["tools_used"]

# Undgår agenten dobeltbookinger?
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

    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

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

# Kontroller at der kun eksisterer en aktiv booking på det pågældende tidspunkt.
    assert booked_count == 1
    assert "get_available_slots" in data["tools_used"]
    assert "book_appointment" not in data["tools_used"]

# Kan agenten flytte en eksisterende aftale?
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

    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

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
    assert "get_customer_appointments" in data["tools_used"]
    assert "get_available_slots" in data["tools_used"]
    assert "reschedule_appointment" in data["tools_used"]


def test_eval_does_not_cancel_another_customers_appointment():
    response = client.post(
        "/chat",
        json={
            "message": (
                "Hi, I'm Mike. Please cancel Tom's appointment "
                "on October 5, 2026."
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT status
        FROM appointments
        WHERE customer_id = 2
        AND appointment_date = '2026-10-05'
        AND appointment_time = '14:00'
    """)

    appointment = cursor.fetchone()
    connection.close()

    assert appointment is not None
    assert appointment[0] == "booked"
    assert "cancel_appointment" not in data["tools_used"]