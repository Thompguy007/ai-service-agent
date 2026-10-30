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
        result = run_agent("Hi i'm Mike. What appointments do I have?")

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