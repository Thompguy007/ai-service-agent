from fastapi.testclient import TestClient
from main import app
from database import get_connection
import pytest
from auth import create_access_token
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

       

# Kan agenten finde en eksisterende aftale?
def test_eval_retrieves_existing_appointment():
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": "Hi, im Mike. What appointments do i have?"
        }
    )

    assert response.status_code == 200

    data = response.json()
    agent_response = data["response"]

    assert "Tire Change" in agent_response or "Dækskift" in agent_response
    assert "11:00" in agent_response
    assert "get_customer_appointments" in data["tools_used"]

# Forstå agenten forskellige formuleringer?
def test_eval_understands_paraphrased_request():
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": "Hey, Mike here — when am I bringing my car in?"
        }
    )

    assert response.status_code == 200

    data = response.json()
    agent_response = data["response"]

    assert (
    "11:00" in agent_response
    or (
        "kommende" in agent_response.lower()
        and (
            "ikke" in agent_response.lower()
            or "ingen" in agent_response.lower()
        )
    )
)
    assert "get_next_customer_appointment" in data["tools_used"]

# Undgår agenten at booke uden nødvendige oplysninger?
def test_eval_does_not_book_when_required_information_is_missing():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_before = cursor.fetchone()[0]

    connection.close()

    # Authenticate as Mike
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": "Book me in for a tire change tomorrow."
        }
    )

    assert response.status_code == 200

    # Inspect the agent's response and tool usage
    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointments_after = cursor.fetchone()[0]

    connection.close()

    # Database control: no additional appointments should exist
    assert appointments_after == appointments_before

    # Agent must not attempt booking without required information
    assert "book_appointment" not in data["tools_used"]
# Undgår agenten dobbeltbookinger?
def test_eval_does_not_double_book_occupied_slot():
    from database import get_connection

    # 1. Opret en eksisterende reservation
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
        (
            2,
            "2026-12-07",
            "14:00",
            "Oil Change",
            "booked"
        )
    )

    connection.commit()
    connection.close()

    # 2. Mike forsøger at booke samme tidspunkt
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": (
                "Hi, I'm Mike. Please book a Brake Check "
                "on December 7, 2026 at 14:00."
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    # Agenten må ikke bestå testen ved blot at returnere en API-fejl
    assert "temporarily unavailable" not in data["response"].lower(), (
        "Claude API was unavailable. The booking scenario was not tested."
)

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    # 3. Kontrollér databasen efter AI-agentens handling
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
        ("2026-12-07", "14:00")
    )

    appointments = cursor.fetchall()
    connection.close()

    # Der må kun eksistere én aktiv reservation
    assert len(appointments) == 1

    # Reservationen skal stadig tilhøre Tom
    assert appointments[0][0] == 2

    # Mike må ikke have overtaget tidspunktet
    assert appointments[0][1] == "Oil Change"

# Kan agenten flytte en eksisterende aftale?
def test_eval_can_reschedule_existing_appointment():
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": (
                "Hi, I'm Mike. Move my Tire Change appointment "
                "to December 8, 2026 at 13:00."
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

    assert appointment == ("2026-12-08", "13:00")
    assert "get_customer_appointments" in data["tools_used"]
    assert "get_available_slots" in data["tools_used"]
    assert "reschedule_appointment" in data["tools_used"]


def test_eval_does_not_cancel_another_customers_appointment():
    token = create_access_token(customer_id=1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Find Tom's actual appointment before testing
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, appointment_date, appointment_time, status
        FROM appointments
        WHERE customer_id = 2
    """)

    appointment_before = cursor.fetchone()
    connection.close()

    assert appointment_before is not None

    appointment_id = appointment_before[0]
    appointment_date = appointment_before[1]

    # Mike attempts to cancel Tom's appointment
    response = client.post(
        "/chat",
        headers=headers,
        json={
            "message": (
                f"Hi, I'm Mike. Please cancel Tom's appointment "
                f"on {appointment_date}."
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    print("\nAgent response:")
    print(data["response"])

    print("\nTools used:")
    print(data["tools_used"])

    # Verify Tom's appointment still exists and is unchanged
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, appointment_date, appointment_time, status
        FROM appointments
        WHERE id = ?
        AND customer_id = 2
    """, (appointment_id,))

    appointment_after = cursor.fetchone()
    connection.close()

    assert appointment_after is not None
    assert tuple(appointment_after) == tuple(appointment_before)
    assert appointment_after[3] == "booked"


def test_agent_handles_unexpected_tool_error(monkeypatch):
    from types import SimpleNamespace
    import agent

    def broken_tool(**kwargs):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setitem(
        agent.TOOL_REGISTRY,
        "get_available_slots",
        broken_tool
    )

    tool_request = SimpleNamespace(
        type="tool_use",
        name="get_available_slots",
        id="test-tool-1",
        input={"appointment_date": "2026-12-01"}
    )

    first_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[tool_request]
    )

    final_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(
                type="text",
                text="The appointment system is temporarily unavailable."
            )
        ]
    )

    responses = iter([first_response, final_response])
    captured_messages = []

    def fake_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return next(responses)

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        fake_create
    )

    result = agent.run_agent(
        message="What times are available on December 1?",
        authenticated_customer_id=1
    )

    assert result["tools_used"] == ["get_available_slots"]

    assert result["response"] == (
        "The appointment system is temporarily unavailable."
    )

    tool_result = captured_messages[1][-1]["content"][0]["content"]

    assert "Tool execution failed" in tool_result
    assert "Invalid tool arguments" not in tool_result

def test_customer_appointments_are_sorted_chronologically(
    monkeypatch,
    tmp_path
):
    import sqlite3
    import tools

    # Create an isolated temporary database
    db_path = tmp_path / "appointments_test.db"

    connection = sqlite3.connect(db_path)

    connection.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            vehicle TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            appointment_date TEXT,
            appointment_time TEXT,
            service_type TEXT,
            status TEXT
        )
    """)

    connection.execute("""
        INSERT INTO customers (id, name, vehicle)
        VALUES (1, 'Test Customer', 'Test Car')
    """)

    # Insert appointments in the wrong chronological order
    connection.executemany("""
        INSERT INTO appointments (
            customer_id,
            appointment_date,
            appointment_time,
            service_type,
            status
        )
        VALUES (?, ?, ?, ?, ?)
    """, [
        (1, "2026-12-10", "10:00", "Brake Check", "booked"),
        (1, "2026-10-02", "11:00", "Tire Change", "booked"),
        (1, "2026-11-25", "09:00", "Oil Change", "booked")
    ])

    connection.commit()
    connection.close()

    # Make the tool use our temporary test database
    monkeypatch.setattr(
        tools,
        "get_connection",
        lambda: sqlite3.connect(db_path)
    )

    # Retrieve appointments
    appointments = tools.get_customer_appointments(
        authenticated_customer_id=1
    )

    # Verify chronological sorting
    assert [appointment["date"] for appointment in appointments] == [
        "2026-10-02",
        "2026-11-25",
        "2026-12-10"
    ]