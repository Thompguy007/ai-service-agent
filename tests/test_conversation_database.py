import sqlite3
import pytest

from database import create_database, create_conversation, get_connection

from database import (
    create_database,
    create_conversation,
    get_connection,
    save_message,
    get_customer_conversations,
    conversation_belongs_to_customer
)

from database import (
    create_database,
    create_conversation,
    get_connection,
    save_message,
    get_conversation_messages,
    save_message_pair
)

def test_create_conversation(monkeypatch, tmp_path):
    # Use an isolated SQLite database.
    test_db = tmp_path / "conversation_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        # Create a customer for this test.
        cursor = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "12345678", "Citroen Berlingo")
        )

        customer_id = cursor.lastrowid
        connection.commit()

    finally:
        connection.close()

    # Create a conversation for the customer.
    conversation_id = create_conversation(customer_id)

    assert isinstance(conversation_id, int)
    assert conversation_id > 0

    # Verify that the conversation was saved.
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT customer_id
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,)
        ).fetchone()

        assert row is not None
        assert row[0] == customer_id

    finally:
        connection.close()

def test_save_conversation_messages(monkeypatch, tmp_path):
    test_db = tmp_path / "messages_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "12345678", "Citroen Berlingo")
        )

        customer_id = cursor.lastrowid
        connection.commit()

    finally:
        connection.close()

    conversation_id = create_conversation(customer_id)

    user_message_id = save_message(
        conversation_id,
        "user",
        "My car is called Blue Rocket."
    )

    assistant_message_id = save_message(
        conversation_id,
        "assistant",
        "Got it! Blue Rocket it is!"
    )

    assert user_message_id > 0
    assert assistant_message_id > user_message_id

    connection = get_connection()

    try:
        messages = connection.execute(
            """
            SELECT role, content
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conversation_id,)
        ).fetchall()

        assert messages == [
            ("user", "My car is called Blue Rocket."),
            ("assistant", "Got it! Blue Rocket it is!"),
        ]

    finally:
        connection.close()

def test_conversation_messages_are_customer_isolated(
    monkeypatch,
    tmp_path
):
    test_db = tmp_path / "isolation_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        mike = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "11111111", "Citroen Berlingo")
        ).lastrowid

        tom = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Tom", "22222222", "BMW")
        ).lastrowid

        connection.commit()

    finally:
        connection.close()

    mike_conversation = create_conversation(mike)
    tom_conversation = create_conversation(tom)

    save_message(
        mike_conversation,
        "user",
        "My car is Blue Rocket."
    )

    save_message(
        tom_conversation,
        "user",
        "My car is Red Dragon."
    )

    # Mike can read his own messages.
    mike_messages = get_conversation_messages(
        mike_conversation,
        mike
    )

    assert mike_messages == [
        {
            "role": "user",
            "content": "My car is Blue Rocket."
        }
    ]

    # Mike cannot read Tom's conversation.
    unauthorized_messages = get_conversation_messages(
        tom_conversation,
        mike
    )

    assert unauthorized_messages == []

    # Tom can read his own messages.
    tom_messages = get_conversation_messages(
        tom_conversation,
        tom
    )

    assert tom_messages == [
        {
            "role": "user",
            "content": "My car is Red Dragon."
        }
    ]

def test_get_customer_conversations(monkeypatch, tmp_path):
    test_db = tmp_path / "conversation_list_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        mike = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "11111111", "Citroen Berlingo")
        ).lastrowid

        tom = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Tom", "22222222", "BMW")
        ).lastrowid

        connection.commit()

    finally:
        connection.close()

    mike_first = create_conversation(mike)
    mike_second = create_conversation(mike)
    tom_conversation = create_conversation(tom)

    mike_conversations = get_customer_conversations(mike)

    assert len(mike_conversations) == 2

    assert [
        conversation["conversation_id"]
        for conversation in mike_conversations
    ] == [mike_second, mike_first]

    assert all(
        conversation["conversation_id"] != tom_conversation
        for conversation in mike_conversations
    )

    tom_conversations = get_customer_conversations(tom)

    assert len(tom_conversations) == 1
    assert tom_conversations[0]["conversation_id"] == tom_conversation

def test_conversation_ownership(monkeypatch, tmp_path):
    test_db = tmp_path / "ownership_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        mike = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "11111111", "Citroen Berlingo")
        ).lastrowid

        tom = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Tom", "22222222", "BMW")
        ).lastrowid

        connection.commit()

    finally:
        connection.close()

    mike_conversation = create_conversation(mike)
    tom_conversation = create_conversation(tom)

    # Mike owns his conversation.
    assert conversation_belongs_to_customer(
        mike_conversation,
        mike
    ) is True

    # Mike cannot access Tom's conversation.
    assert conversation_belongs_to_customer(
        tom_conversation,
        mike
    ) is False

    # Tom owns his conversation.
    assert conversation_belongs_to_customer(
        tom_conversation,
        tom
    ) is True

    # Nonexistent conversations must be rejected.
    assert conversation_belongs_to_customer(
        999999,
        mike
    ) is False

def test_save_message_pair(monkeypatch, tmp_path):
    test_db = tmp_path / "message_pair_test.db"
    monkeypatch.setenv("DB_NAME", str(test_db))

    create_database()

    connection = get_connection()

    try:
        customer_id = connection.execute(
            """
            INSERT INTO customers (name, phone, vehicle)
            VALUES (?, ?, ?)
            """,
            ("Mike", "12345678", "Citroen Berlingo")
        ).lastrowid

        connection.commit()

    finally:
        connection.close()

    conversation_id = create_conversation(customer_id)

    save_message_pair(
        conversation_id,
        "My car is Blue Rocket.",
        "Got it! Blue Rocket it is!"
    )

    messages = get_conversation_messages(
        conversation_id,
        customer_id
    )

    assert messages == [
        {
            "role": "user",
            "content": "My car is Blue Rocket."
        },
        {
            "role": "assistant",
            "content": "Got it! Blue Rocket it is!"
        }
    ]

def test_message_pair_rolls_back_if_second_insert_fails():
    # Create a conversation for customer 1.
    conversation_id = create_conversation(customer_id=1)

    connection = get_connection()

    try:
        # Reject assistant messages to simulate a database failure
        # after the user message has been inserted.
        connection.execute(
            """
            CREATE TRIGGER fail_assistant_insert
            BEFORE INSERT ON conversation_messages
            WHEN NEW.role = 'assistant'
            BEGIN
                SELECT RAISE(ABORT, 'Simulated database failure');
            END;
            """
        )

        connection.commit()

    finally:
        connection.close()

    # Saving the pair must fail.
    with pytest.raises(sqlite3.IntegrityError):
        save_message_pair(
            conversation_id=conversation_id,
            user_message="I need a tire change",
            assistant_message="Sure, I can help!"
        )

    # Neither message should have been saved.
    messages = get_conversation_messages(
        conversation_id=conversation_id,
        customer_id=1
    )

    assert messages == []