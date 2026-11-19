from unittest.mock import patch

from fastapi.testclient import TestClient

from auth import create_access_token
from main import app, conversation_histories, conversation_lock

client = TestClient(app)


def clear_history():
    with conversation_lock:
        conversation_histories.clear()


def send_chat(customer_id, message):
    token = create_access_token(customer_id=customer_id)

    return client.post(
        "/chat",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"}
    )


def test_customer_remembers_previous_messages():
    clear_history()

    with patch("main.run_agent") as mock_agent:
        mock_agent.side_effect = [
            {"response": "Your nickname is Blue Rocket.", "tools_used": []},
            {"response": "You called it Blue Rocket.", "tools_used": []},
        ]

        first = send_chat(1, "My car is called Blue Rocket.")
        second = send_chat(1, "What did I call my car?")

        assert first.status_code == 200
        assert second.status_code == 200

        assert mock_agent.call_count == 2

        second_call = mock_agent.call_args_list[1]

        assert second_call.kwargs["conversation_history"] == [
            {
                "role": "user",
                "content": "My car is called Blue Rocket."
            },
            {
                "role": "assistant",
                "content": "Your nickname is Blue Rocket."
            }
        ]


def test_customers_have_separate_conversations():
    clear_history()

    with patch("main.run_agent") as mock_agent:
        mock_agent.side_effect = [
            {"response": "Hello Mike!", "tools_used": []},
            {"response": "Hello Tom!", "tools_used": []},
        ]

        mike_response = send_chat(1, "My secret word is Pineapple.")
        tom_response = send_chat(2, "Hello!")

        assert mike_response.status_code == 200
        assert tom_response.status_code == 200

        tom_call = mock_agent.call_args_list[1]

        assert tom_call.kwargs["authenticated_customer_id"] == 2
        assert tom_call.kwargs["conversation_history"] == []

        assert conversation_histories[1] == [
            {"role": "user", "content": "My secret word is Pineapple."},
            {"role": "assistant", "content": "Hello Mike!"},
        ]

        assert conversation_histories[2] == [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hello Tom!"},
        ]


def test_conversation_history_is_limited():
    from rate_limiter import RateLimiter

    clear_history()

    # Allow enough requests to test conversation history independently.
    test_limiter = RateLimiter(
        max_requests=20,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:
            mock_agent.return_value = {
                "response": "Message received.",
                "tools_used": []
            }

            for index in range(15):
                response = send_chat(1, f"Message {index}")
                assert response.status_code == 200

            assert mock_agent.call_count == 15

    assert len(conversation_histories[1]) == 20
    assert conversation_histories[1][0]["content"] == "Message 5"
    assert conversation_histories[1][-1]["content"] == "Message received."

def test_clear_chat_history_only_affects_authenticated_customer():
    clear_history()

    try:
        # Create separate conversation histories for Mike and Tom.
        with conversation_lock:
            conversation_histories[1] = [
                {"role": "user", "content": "My car is Blue Rocket."},
                {"role": "assistant", "content": "Got it!"},
            ]

            conversation_histories[2] = [
                {"role": "user", "content": "My car is Red Dragon."},
                {"role": "assistant", "content": "Got it!"},
            ]

        # Mike requests a new conversation.
        token = create_access_token(customer_id=1)

        response = client.delete(
            "/chat/history",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Mike's history should be deleted.
        assert 1 not in conversation_histories

        # Tom's history must remain untouched.
        assert conversation_histories[2] == [
            {"role": "user", "content": "My car is Red Dragon."},
            {"role": "assistant", "content": "Got it!"},
        ]

    finally:
        clear_history()


def test_clear_chat_history_requires_authentication():
    clear_history()

    try:
        # Create an existing conversation.
        with conversation_lock:
            conversation_histories[1] = [
                {"role": "user", "content": "Private message."}
            ]

        # Attempt deletion without JWT.
        response = client.delete("/chat/history")

        assert response.status_code == 401

        # The conversation must still exist.
        assert conversation_histories[1] == [
            {"role": "user", "content": "Private message."}
        ]

    finally:
        clear_history()