from fastapi.testclient import TestClient
import sqlite3
from main import app



def test_customer_can_create_conversation(auth_headers):
    client = TestClient(app)

    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201

    data = response.json()

    assert "conversation_id" in data
    assert isinstance(data["conversation_id"], int)
    assert data["conversation_id"] > 0

from auth import create_access_token


def test_customer_cannot_read_another_customers_conversation(auth_headers):
    client = TestClient(app)

    # Customer 1 creates a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201

    conversation_id = response.json()["conversation_id"]

    # Customer 2 attempts to access customer 1's conversation
    other_customer_token = create_access_token(customer_id=2)

    other_customer_headers = {
        "Authorization": f"Bearer {other_customer_token}"
    }

    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=other_customer_headers
    )

    # The conversation must not be accessible
    assert response.status_code == 404

def test_customer_cannot_write_to_another_customers_conversation(auth_headers):
    client = TestClient(app)

    # Customer 1 creates a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201

    conversation_id = response.json()["conversation_id"]

    # Customer 2 attempts to send a message
    other_customer_token = create_access_token(customer_id=2)

    other_customer_headers = {
        "Authorization": f"Bearer {other_customer_token}"
    }

    response = client.post(
        f"/conversations/{conversation_id}/chat",
        headers=other_customer_headers,
        json={
            "message": "Hello, I want to access this conversation."
        }
    )

    # Customer 2 must be denied access
    assert response.status_code == 404

    # Verify that no messages were added
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_conversation_endpoints_require_authentication():
    client = TestClient(app)

    # Attempt to create a conversation without authentication
    response = client.post("/conversations")
    assert response.status_code == 401

    # Attempt to retrieve conversations without authentication
    response = client.get("/conversations")
    assert response.status_code == 401

    # Attempt to retrieve messages without authentication
    response = client.get("/conversations/1/messages")
    assert response.status_code == 401

    # Attempt to send a message without authentication
    response = client.post(
        "/conversations/1/chat",
        json={"message": "Hello"}
    )
    assert response.status_code == 401

def test_conversation_endpoints_reject_invalid_token():
    client = TestClient(app)

    invalid_headers = {
        "Authorization": "Bearer this.is.not.a.valid.jwt"
    }

    response = client.post(
        "/conversations",
        headers=invalid_headers
    )
    assert response.status_code == 401

    response = client.get(
        "/conversations",
        headers=invalid_headers
    )
    assert response.status_code == 401

    response = client.get(
        "/conversations/1/messages",
        headers=invalid_headers
    )
    assert response.status_code == 401

    response = client.post(
        "/conversations/1/chat",
        headers=invalid_headers,
        json={"message": "Hello"}
    )
    assert response.status_code == 401

def test_customers_only_see_their_own_conversations(auth_headers):
    client = TestClient(app)

    # Customer 1 creates two conversations
    mike_ids = []

    for _ in range(2):
        response = client.post(
            "/conversations",
            headers=auth_headers
        )

        assert response.status_code == 201
        mike_ids.append(response.json()["conversation_id"])

    # Customer 2 creates one conversation
    tom_token = create_access_token(customer_id=2)

    tom_headers = {
        "Authorization": f"Bearer {tom_token}"
    }

    response = client.post(
        "/conversations",
        headers=tom_headers
    )

    assert response.status_code == 201
    tom_id = response.json()["conversation_id"]

    # Customer 1 retrieves their conversations
    response = client.get(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 200

    mike_conversations = response.json()["conversations"]

    mike_returned_ids = {
        conversation["conversation_id"]
        for conversation in mike_conversations
    }

    assert mike_returned_ids == set(mike_ids)

    # Customer 2 retrieves their conversations
    response = client.get(
        "/conversations",
        headers=tom_headers
    )

    assert response.status_code == 200

    tom_conversations = response.json()["conversations"]

    tom_returned_ids = {
        conversation["conversation_id"]
        for conversation in tom_conversations
    }

    assert tom_returned_ids == {tom_id}

from unittest.mock import patch


def test_unauthorized_customer_does_not_trigger_ai(auth_headers):
    client = TestClient(app)

    # Mike creates a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Tom attempts to write to Mike's conversation
    tom_token = create_access_token(customer_id=2)

    tom_headers = {
        "Authorization": f"Bearer {tom_token}"
    }

    # Monitor whether the AI agent gets called
    with patch("main.run_agent") as mock_agent:
        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=tom_headers,
            json={"message": "Hello"}
        )

        assert response.status_code == 404

        # AI must never be called
        mock_agent.assert_not_called()

def test_successful_ai_chat_saves_messages(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Simulate the AI agent
    with patch("main.run_agent") as mock_agent:
        mock_agent.return_value = {
            "response": "Hello Mike! How can I help you?",
            "tools_used": []
        }

        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": "Hello"}
        )

        assert response.status_code == 200

        mock_agent.assert_called_once()

    # Retrieve messages from SQLite through the API
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200

    messages = response.json()["messages"]

    assert len(messages) == 2

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"

    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hello Mike! How can I help you?"

def test_failed_ai_response_does_not_save_messages(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Simulate an unavailable AI agent
    with patch("main.run_agent") as mock_agent:
        mock_agent.return_value = {
            "response": (
                "The assistant is temporarily unavailable. "
                "Please try again later."
            ),
            "tools_used": []
        }

        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": "I need a tire change"}
        )

        assert response.status_code == 200
        mock_agent.assert_called_once()

    # Retrieve stored messages
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200

    messages = response.json()["messages"]

    # Failed AI interactions must not be saved
    assert messages == []

def test_ai_exception_does_not_save_messages(auth_headers):
    client = TestClient(app, raise_server_exceptions=False)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Simulate an unexpected AI crash
    with patch("main.run_agent") as mock_agent:
        mock_agent.side_effect = RuntimeError("Simulated AI failure")

        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": "I need a tire change"}
        )

        mock_agent.assert_called_once()

    # An unexpected failure must not appear as a successful request
    assert response.status_code == 503

    assert response.json()["detail"] == (
    "The AI assistant is temporarily unavailable. "
    "Please try again later."
)

    # Check that no messages were stored
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_database_failure_does_not_return_success(auth_headers):
    client = TestClient(app, raise_server_exceptions=False)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Simulate a successful AI response,
    # followed by a database failure.
    with patch("main.run_agent") as mock_agent, \
         patch("main.save_message_pair") as mock_save:

        mock_agent.return_value = {
            "response": "Sure, I can help you!",
            "tools_used": []
        }

        mock_save.side_effect = sqlite3.OperationalError(
            "Simulated database failure"
        )

        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": "I need a tire change"}
        )

        mock_agent.assert_called_once()
        mock_save.assert_called_once()

    # The API must not claim success.
    assert response.status_code == 503

    assert response.json()["detail"] == (
    "Unable to save the conversation. Please try again later."
)

    # No messages should have been stored.
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_empty_message_is_rejected_without_calling_ai(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Attempt to send an empty message
    with patch("main.run_agent") as mock_agent:
        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": ""}
        )

        # Invalid input must never reach Claude
        mock_agent.assert_not_called()

    # FastAPI should reject the request
    assert response.status_code == 422

    # Invalid messages must not be stored
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_whitespace_message_is_rejected_without_calling_ai(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Attempt to send a message containing only spaces
    with patch("main.run_agent") as mock_agent:
        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": "       "}
        )

        # Invalid input must never reach Claude
        mock_agent.assert_not_called()

    # FastAPI should reject the message
    assert response.status_code == 422

    # No messages should be stored
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_message_over_max_length_is_rejected(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Generate a message containing 4001 characters
    long_message = "A" * 4001

    # Attempt to send the oversized message
    with patch("main.run_agent") as mock_agent:
        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": long_message}
        )

        # Invalid input must never reach Claude
        mock_agent.assert_not_called()

    # FastAPI should reject the message
    assert response.status_code == 422

    # Verify that nothing was saved
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_message_at_max_length_is_accepted(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Exactly 4000 characters
    max_length_message = "A" * 4000

    # Mock Claude to avoid real API calls
    with patch("main.run_agent") as mock_agent:
        mock_agent.return_value = {
            "response": "Message received successfully.",
            "tools_used": []
        }

        response = client.post(
            f"/conversations/{conversation_id}/chat",
            headers=auth_headers,
            json={"message": max_length_message}
        )

        # Valid input should reach the AI agent
        mock_agent.assert_called_once()

        # Verify the exact message was passed to Claude
        assert (
            mock_agent.call_args.kwargs["message"]
            == max_length_message
        )

    # The API should accept the message
    assert response.status_code == 200

    # Both messages should be saved
    response = client.get(
        f"/conversations/{conversation_id}/messages",
        headers=auth_headers
    )

    assert response.status_code == 200

    messages = response.json()["messages"]

    assert len(messages) == 2
    assert messages[0]["content"] == max_length_message
    assert messages[1]["content"] == "Message received successfully."

def test_legacy_chat_rejects_invalid_messages(auth_headers):
    client = TestClient(app)

    invalid_messages = [
        "",
        "       ",
        "A" * 4001
    ]

    with patch("main.run_agent") as mock_agent:

        for message in invalid_messages:
            response = client.post(
                "/chat",
                headers=auth_headers,
                json={"message": message}
            )

            assert response.status_code == 422

        # None of the invalid messages should reach Claude
        mock_agent.assert_not_called()

def test_chat_rate_limit_returns_429(auth_headers):
    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Use a fresh limiter for this test
    from rate_limiter import RateLimiter

    test_limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:

            mock_agent.return_value = {
                "response": "Test response",
                "tools_used": []
            }

            # First 10 requests should succeed
            for _ in range(10):
                response = client.post(
                    f"/conversations/{conversation_id}/chat",
                    headers=auth_headers,
                    json={"message": "Hello"}
                )

                assert response.status_code == 200

            # Request number 11 should be blocked
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": "Hello again"}
            )

            assert response.status_code == 429

            # Claude must only be called 10 times
            assert mock_agent.call_count == 10

def test_invalid_message_does_not_use_rate_limit(auth_headers):
    from rate_limiter import RateLimiter

    client = TestClient(app)

    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    test_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:

            mock_agent.return_value = {
                "response": "Hello!",
                "tools_used": []
            }

            # Invalid message should be rejected
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": ""}
            )

            assert response.status_code == 422
            mock_agent.assert_not_called()

            # First valid message should still be allowed
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": "Hello"}
            )

            assert response.status_code == 200
            assert mock_agent.call_count == 1

            # Second valid message should be blocked
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": "Hello again"}
            )

            assert response.status_code == 429
            assert mock_agent.call_count == 1

def test_rate_limit_is_independent_per_customer(auth_headers):
    from rate_limiter import RateLimiter

    client = TestClient(app)

    # Customer 1
    response = client.post(
        "/conversations",
        headers=auth_headers
    )
    assert response.status_code == 201
    conversation_1 = response.json()["conversation_id"]

    # Customer 2
    token_2 = create_access_token(customer_id=2)
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    response = client.post(
        "/conversations",
        headers=headers_2
    )
    assert response.status_code == 201
    conversation_2 = response.json()["conversation_id"]

    # Only one request per customer
    test_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:

            mock_agent.return_value = {
                "response": "Hello!",
                "tools_used": []
            }

            # Customer 1 uses their quota
            response = client.post(
                f"/conversations/{conversation_1}/chat",
                headers=auth_headers,
                json={"message": "Hello"}
            )
            assert response.status_code == 200

            # Customer 1 is blocked
            response = client.post(
                f"/conversations/{conversation_1}/chat",
                headers=auth_headers,
                json={"message": "Hello again"}
            )
            assert response.status_code == 429

            # Customer 2 should still be allowed
            response = client.post(
                f"/conversations/{conversation_2}/chat",
                headers=headers_2,
                json={"message": "Hello"}
            )
            assert response.status_code == 200

            # Exactly two AI calls
            assert mock_agent.call_count == 2

def test_rate_limit_returns_retry_after_header(auth_headers):
    from rate_limiter import RateLimiter

    client = TestClient(app)

    # Create a conversation
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Allow only one request
    test_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:

            mock_agent.return_value = {
                "response": "Hello!",
                "tools_used": []
            }

            # First request succeeds
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": "Hello"}
            )

            assert response.status_code == 200

            # Second request is blocked
            response = client.post(
                f"/conversations/{conversation_id}/chat",
                headers=auth_headers,
                json={"message": "Hello again"}
            )

            assert response.status_code == 429

            # Verify Retry-After header
            assert "retry-after" in response.headers

            retry_after = int(response.headers["retry-after"])

            assert 1 <= retry_after <= 60

            # Claude should only be called once
            assert mock_agent.call_count == 1

def test_rate_limit_is_shared_between_chat_endpoints(auth_headers):
    from rate_limiter import RateLimiter

    client = TestClient(app)

    # Create a conversation for the authenticated customer
    response = client.post(
        "/conversations",
        headers=auth_headers
    )

    assert response.status_code == 201
    conversation_id = response.json()["conversation_id"]

    # Use a fresh limiter shared by both endpoints
    test_limiter = RateLimiter(
        max_requests=10,
        window_seconds=60
    )

    with patch("main.chat_rate_limiter", test_limiter):
        with patch("main.run_agent") as mock_agent:

            mock_agent.return_value = {
                "response": "Test response",
                "tools_used": []
            }

            # Use five requests on the original chat endpoint
            for _ in range(5):
                response = client.post(
                    "/chat",
                    headers=auth_headers,
                    json={"message": "Hello"}
                )

                assert response.status_code == 200

                print("Agent calls after /chat:", mock_agent.call_count)
            # Use five requests on the conversation endpoint
            for _ in range(5):
                response = client.post(
                    f"/conversations/{conversation_id}/chat",
                    headers=auth_headers,
                    json={"message": "Hello"}
                )

                assert response.status_code == 200

            print("Agent calls after conversation chat:", mock_agent.call_count)

            # Both endpoints must now reject additional requests
            for endpoint in (
                "/chat",
                f"/conversations/{conversation_id}/chat"
            ):
                response = client.post(
                    endpoint,
                    headers=auth_headers,
                    json={"message": "One more request"}
                )

                assert response.status_code == 429
                assert "retry-after" in response.headers

                print("\nRecorded agent calls:", mock_agent.call_count)
                for call in mock_agent.call_args_list:
                    print("Message:", call.kwargs.get("message"))

            # Only the ten allowed requests reached the AI agent
            assert mock_agent.call_count == 10