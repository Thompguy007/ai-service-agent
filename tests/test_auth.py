import jwt
from database import get_connection

from auth import (
    authenticate_customer,
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
    JWT_SECRET_KEY,
    JWT_ALGORITHM
)

def test_password_is_hashed():
    password = "MySecretPassword123"

    hashed = hash_password(password)

    # The password must not be stored in plaintext
    assert hashed != password

    # Argon2 should be used
    assert hashed.startswith("$argon2")


def test_correct_password_is_verified():
    password = "MySecretPassword123"

    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_wrong_password_is_rejected():
    password = "MySecretPassword123"

    hashed = hash_password(password)

    assert verify_password("WrongPassword123", hashed) is False

def test_create_access_token():
    # Generate a token for customer 1
    token = create_access_token(customer_id=1)

    # Verify the token's signature and expiration
    payload = jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM]
    )

    # Check the customer identity
    assert payload["sub"] == "1"

    # Check that the token has an expiration
    assert "exp" in payload

def test_valid_access_token():
    token = create_access_token(customer_id=1)

    customer_id = verify_access_token(token)

    assert customer_id == 1


def test_invalid_access_token():
    token = "this.is.not.a.valid.token"

    customer_id = verify_access_token(token)

    assert customer_id is None


def test_expired_access_token():
    from datetime import datetime, timedelta, timezone

    expired_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5)
    }

    expired_token = jwt.encode(
        expired_payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    customer_id = verify_access_token(expired_token)

    assert customer_id is None

def test_authenticate_customer_with_correct_password():
    password = "SecureTestPassword123!"

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

    customer_id = authenticate_customer(
        email="mike@example.com",
        password=password
    )

    assert customer_id == 1

def test_authenticate_customer_with_wrong_password():
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

    customer_id = authenticate_customer(
        email="mike@example.com",
        password="WrongPassword123!"
    )

    assert customer_id is None
def test_authenticate_customer_with_nonexistent_email():
    customer_id = authenticate_customer(
        email="unknown@example.com",
        password="SomePassword123!"
    )

    assert customer_id is None