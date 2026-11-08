from pwdlib import PasswordHash
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError


load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 30

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is missing from environment")


# Secure password hashing using Argon2
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password
    )

def create_access_token(customer_id: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(
        minutes=JWT_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(customer_id),
        "exp": expiration
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    return token

def verify_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]}
        )

        customer_id = int(payload["sub"])

        if customer_id <= 0:
            return None

        return customer_id

    except (InvalidTokenError, ValueError, TypeError):
        return None

from database import get_connection


def authenticate_customer(email: str, password: str) -> int | None:
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, password_hash
            FROM customers
            WHERE email = ?
            """,
            (email,)
        )

        customer = cursor.fetchone()

    finally:
        connection.close()

    if customer is None:
        return None

    customer_id, stored_password_hash = customer

    if not stored_password_hash:
        return None

    if not verify_password(password, stored_password_hash):
        return None

    return customer_id