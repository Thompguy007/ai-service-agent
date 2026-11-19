from unittest.mock import patch
from agent import run_agent

class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text

class FakeToolUseBlock:
    def __init__(self, name, tool_input, tool_id="fake-tool-id"):
        self.type = "tool_use"
        self.name = name
        self.input = tool_input
        self.id = tool_id

def test_agent_returns_mocked_text_response():
    fake_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Hello from fake Claude")
        ]
    )

    with patch("agent.client.messages.create", return_value=fake_response):
        result = run_agent("Hello")

    assert result["response"] == "Hello from fake Claude"

def test_agent_handles_mocked_tool_call():
    tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="get_customer_appointments",
                tool_input={"customer_name": "Mike"}
            )
        ]
    )

    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Mike has a Tire Change appointment at 11:00.")
        ]
    )

    with patch(
        "agent.client.messages.create",
        side_effect=[tool_response, final_response]
    ) as mock_create:
        result = run_agent(
        "Hi i'm Mike. What appointments do I have?",
        authenticated_customer_id=1
)

        assert mock_create.call_count == 2
        second_call = mock_create.call_args_list[1]
        second_call_messages = second_call.kwargs["messages"]
        tool_result_message = second_call_messages[-1]
        assert tool_result_message["role"] == "user"
        tool_results = tool_result_message["content"]
        first_tool_result = tool_results[0]
        assert first_tool_result["type"] == "tool_result"
        assert result["response"] == "Mike has a Tire Change appointment at 11:00."
        assert "Tire Change" in first_tool_result["content"]
        assert "11:00" in first_tool_result["content"]

# jeg vil kalde "delete_entire_database." 
# men det tool findes ikke i vores tilladte routing i agent.py. 
# og agenten skal nægte at udføre noget.
def test_agent_handles_unknown_tool_safely():
        tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="delete_entire_database",
                tool_input={}
            )
        ]
    )
        final_response = FakeResponse(
            stop_reason="end_turn",
            content=[
                FakeTextBlock("I cannot perform that action.")
            ]
        )

        with patch(
            "agent.client.messages.create",
            side_effect=[tool_response, final_response]
        ) as mock_create:
            result = run_agent("Delete the entire database")
        assert mock_create.call_count == 2
        second_call = mock_create.call_args_list[1]
        second_call_messages = second_call.kwargs["messages"]
        tool_result_message = second_call_messages[-1]
        assert tool_result_message["role"] == "user"
        tool_results = tool_result_message["content"]
        first_tool_result = tool_results[0]
        assert first_tool_result["type"] == "tool_result"
        assert "Unknown tool" in first_tool_result["content"]

def test_agent_handles_missing_tool_arguments_safely():
    tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="book_appointment",
                tool_input={
                    "appointment_date": "2026-11-10",
                    "appointment_time": "10:00"
                }
            )
        ]
    )

    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("I need more information before i can book the appointment.")
        ]
    )

    with patch(
        "agent.client.messages.create",
        side_effect=[tool_response, final_response]
    ):
        result = run_agent("Book me an appointment")

        assert result["response"] == "I need more information before i can book the appointment."

def test_agent_reports_step_count():
    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Hello! How can i help you?")
        ]
    )

    with patch(
        "agent.client.messages.create",
        return_value=final_response
    ):
        result = run_agent("Hello")
    assert result["steps"] == 1

def test_agent_reports_two_steps_after_tool_call():
    tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="get_customer_appointments",
                tool_input={"customer_name": "Mike"}
            )
        ]
    )

    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Mike has an appointment.")
        ]
    )

    with patch(
        "agent.client.messages.create",
        side_effect=[tool_response, final_response]
    ):
        result = run_agent("What appointments does Mike have?")

    assert result["steps"] == 2

def test_agent_reports_tools_used():
    tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="get_customer_appointments",
                tool_input={"customer_name": "Mike"}
            )
        ]
    )

    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Mike has an appointment.")
        ]
    )

    with patch(
        "agent.client.messages.create",
        side_effect=[tool_response, final_response]
    ):
        result = run_agent("What appointments does Mike have?")

    assert result["tools_used"] == ["get_customer_appointments"]

def test_agent_reports_multiple_tools_used():
    tool_response = FakeResponse(
        stop_reason="tool_use",
        content=[
            FakeToolUseBlock(
                name="get_available_slots",
                tool_input={"appointment_date": "2026-11-10"}
            ),
            FakeToolUseBlock(
                name="book_appointment",
                tool_input={
                    "customer_id": 1,
                    "appointment_time": "10:00",
                    "service_type": "service"
                }
            )
        ]
    )

    final_response = FakeResponse(
        stop_reason="end_turn",
        content=[
            FakeTextBlock("Your appointment has been booked.")
        ]
    )

    with patch(
        "agent.client.messages.create",
        side_effect=[tool_response, final_response]
    ):
        result = run_agent("Book Mike for service on November 10 at 10:00")

    assert result["tools_used"] == [
        "get_available_slots",
        "book_appointment"
    ]

from types import SimpleNamespace
from unittest.mock import patch


def test_agent_handles_empty_response():
    """Agent must never return an empty response."""

    mock_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(
                type="text",
                text=""
            )
        ]
    )

    with patch("agent.client.messages.create", return_value=mock_response):
        result = run_agent(
            "What appointments do I have?",
            authenticated_customer_id=1
        )

    assert result["response"].strip()
    assert result["response"] == (
        "I couldn't generate a complete response. "
        "Please try again."
    )
    assert result["steps"] == 1

def test_agent_handles_max_tokens():
    """Agent must not return a truncated response as complete."""

    mock_response = SimpleNamespace(
        stop_reason="max_tokens",
        content=[
            SimpleNamespace(
                type="text",
                text="Your appointment has been"
            )
        ]
    )

    with patch("agent.client.messages.create", return_value=mock_response):
        result = run_agent(
            "What appointments do I have?",
            authenticated_customer_id=1
        )

    assert result["response"] == (
        "I couldn't complete my response. "
        "Please try again."
    )

    assert result["steps"] == 1
    assert result["tools_used"] == []

def test_agent_handles_unexpected_tool_error(monkeypatch):
    """Agent should handle unexpected tool failures safely."""

    from types import SimpleNamespace
    import agent

    def fake_tool(**kwargs):
        raise RuntimeError("Simulated database failure")

    monkeypatch.setitem(
        agent.TOOL_REGISTRY,
        "get_available_slots",
        fake_tool
    )

    tool_call = SimpleNamespace(
        type="tool_use",
        id="tool_123",
        name="get_available_slots",
        input={"appointment_date": "2026-11-12"}
    )

    first_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[tool_call]
    )

    final_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(
                type="text",
                text="Sorry, I couldn't check availability."
            )
        ]
    )

    responses = iter([first_response, final_response])

    monkeypatch.setattr(
        agent.client.messages,
        "create",
        lambda **kwargs: next(responses)
    )

    result = agent.run_agent(
        message="Check available appointments",
        authenticated_customer_id=1
    )

    assert result["response"] == (
        "Sorry, I couldn't check availability."
    )

    assert result["steps"] == 2
    assert result["tools_used"] == ["get_available_slots"]

from unittest.mock import patch, MagicMock


def test_agent_receives_language_instructions():
    from agent import run_agent

    # Simulate Claude's response
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"

    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "Hej! Hvordan kan jeg hjælpe dig?"

    mock_response.content = [mock_text]

    with patch("agent.client.messages.create", return_value=mock_response) as mock_create:

        result = run_agent(
            message="Hej",
            authenticated_customer_id=1
        )

        # Verify that Claude receives the system prompt
        mock_create.assert_called_once()

        system_prompt = mock_create.call_args.kwargs["system"]

        assert "LANGUAGE RULES:" in system_prompt
        assert "Only use Danish as the default" in system_prompt

        # Verify that the agent returns Claude's response
        assert result["response"] == "Hej! Hvordan kan jeg hjælpe dig?"

def test_agent_receives_current_date_and_time():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from unittest.mock import MagicMock, patch
    from agent import run_agent

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"

    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "Hej! Hvordan kan jeg hjælpe?"

    mock_response.content = [mock_text]

    with patch(
        "agent.client.messages.create",
        return_value=mock_response
    ) as mock_create:

        run_agent(
            message="Hvornår er min næste aftale?",
            authenticated_customer_id=1
        )

        system_prompt = mock_create.call_args.kwargs["system"]

        current_date = datetime.now(
            ZoneInfo("Europe/Copenhagen")
        ).strftime("%Y-%m-%d")

        assert f"Today's date is {current_date}" in system_prompt
        assert "Timezone: Europe/Copenhagen" in system_prompt
        assert "Current local time is" in system_prompt

def test_get_next_customer_appointment(monkeypatch):
    import tools
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("Europe/Copenhagen"))

    from datetime import timedelta

    past = now - timedelta(days=10)
    future = now + timedelta(days=5)
    later = now + timedelta(days=15)

    def make_appointment(appointment_id, date, status):
        return {
            "appointment_id": appointment_id,
            "customer_id": 1,
            "date": date.strftime("%Y-%m-%d"),
            "time": date.strftime("%H:%M"),
            "service_type": "Oil Change",
            "status": status
        }

    mock_appointments = [
        make_appointment(1, past, "booked"),
        make_appointment(2, later, "booked"),
        make_appointment(3, future, "cancelled"),
        make_appointment(4, future, "booked")
    ]

    monkeypatch.setattr(
        tools,
        "get_customer_appointments",
        lambda authenticated_customer_id: mock_appointments
    )

    result = tools.get_next_customer_appointment(
        authenticated_customer_id=1
    )

    assert result["success"] is True
    assert result["appointment"]["appointment_id"] == 4

def test_next_appointment_tool_is_registered_and_protected(monkeypatch):
    import agent

    # Verify that Claude can see the tool
    tool_names = [
        tool["name"]
        for tool in agent.appointment_tools
    ]

    assert "get_next_customer_appointment" in tool_names

    # Verify that the tool is registered in the backend
    assert "get_next_customer_appointment" in agent.TOOL_REGISTRY

    # Replace the real database tool with a mock
    captured = {}

    def fake_get_next_customer_appointment(
        authenticated_customer_id=None
    ):
        captured["customer_id"] = authenticated_customer_id

        return {
            "success": True,
            "appointment": None
        }

    monkeypatch.setitem(
        agent.TOOL_REGISTRY,
        "get_next_customer_appointment",
        fake_get_next_customer_appointment
    )

    # Unauthenticated requests must be rejected
    unauthorized = agent.execute_tool(
        tool_name="get_next_customer_appointment",
        tool_input={},
        authenticated_customer_id=None
    )

    assert unauthorized["success"] is False
    assert unauthorized["error"] == "Authentication required"
    assert captured == {}

    # Authenticated requests must use the correct customer ID
    authorized = agent.execute_tool(
        tool_name="get_next_customer_appointment",
        tool_input={},
        authenticated_customer_id=1
    )

    assert authorized["success"] is True
    assert captured["customer_id"] == 1