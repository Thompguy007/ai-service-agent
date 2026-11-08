from unittest.mock import patch

from auth import create_access_token
from fastapi.testclient import TestClient

from database import get_connection
from auth import hash_password, verify_access_token

from main import app


client = TestClient(app)


def test_chat_requires_authentication():
    response = client.post(
        "/chat",
        json={
            "message": "Cancel my appointment"
        }
    )

    assert response.status_code == 401

def test_chat_rejects_invalid_token():
    response = client.post(
        "/chat",
        json={
            "message": "Cancel my appointment"
        },
        headers={
            "Authorization": "Bearer this.is.a.fake.token"
        }
    )

    assert response.status_code == 401

from datetime import datetime, timedelta, timezone

import jwt

from auth import JWT_SECRET_KEY, JWT_ALGORITHM


def test_chat_rejects_expired_token():
    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5)
    }

    expired_token = jwt.encode(
        expired_payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    response = client.post(
        "/chat",
        json={
            "message": "Cancel my appointment"
        },
        headers={
            "Authorization": f"Bearer {expired_token}"
        }
    )

    assert response.status_code == 401

def test_chat_accepts_valid_token():
    token = create_access_token(customer_id=1)

    with patch("main.run_agent") as mock_agent:
        mock_agent.return_value = {
            "response": "Hello Mike!",
            "tools_used": []
        }

        response = client.post(
            "/chat",
            json={
                "message": "Hello!"
            },
            headers={
                "Authorization": f"Bearer {token}"
            }
        )

        assert response.status_code == 200

        mock_agent.assert_called_once_with(
            message="Hello!",
            authenticated_customer_id=1
        )

def test_chat_rejects_nonexistent_customer():
    token = create_access_token(customer_id=999999)

    response = client.post(
        "/chat",
        json={
            "message": "Show my appointments"
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Customer no longer exists"

def test_login_with_correct_credentials():
    password = "SecurePassword123!"

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE customers
            SET email = ?, password_hash = ?
            WHERE id = ?
            """,
            (
                "mike@example.com",
                hash_password(password),
                1
            )
        )

        connection.commit()

    finally:
        connection.close()

    response = client.post(
        "/login",
        json={
            "email": "mike@example.com",
            "password": password
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["token_type"] == "bearer"
    assert "access_token" in data

    customer_id = verify_access_token(
        data["access_token"]
    )

    assert customer_id == 1

def test_login_rejects_wrong_password():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE customers
            SET email = ?, password_hash = ?
            WHERE id = ?
            """,
            (
                "mike@example.com",
                hash_password("CorrectPassword123!"),
                1
            )
        )

        connection.commit()

    finally:
        connection.close()

    response = client.post(
        "/login",
        json={
            "email": "mike@example.com",
            "password": "WrongPassword123!"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_login_rejects_unknown_email():
    response = client.post(
        "/login",
        json={
            "email": "unknown@example.com",
            "password": "SomePassword123!"
        }
    )

    assert response.status_code == 401

    assert response.json()["detail"] == "Invalid email or password"

    assert "access_token" not in response.json()

