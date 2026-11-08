from unittest.mock import Mock, patch

from agent import execute_tool


def test_ai_cannot_override_authenticated_customer_id():
    mock_tool = Mock(return_value={"success": True})

    with patch.dict(
        "agent.TOOL_REGISTRY",
        {"cancel_appointment": mock_tool}
    ):
        result = execute_tool(
            tool_name="cancel_appointment",
            tool_input={
                "appointment_id": 2,
                "authenticated_customer_id": 999
            },
            authenticated_customer_id=1
        )

    mock_tool.assert_called_once_with(
        appointment_id=2,
        authenticated_customer_id=1
    )

    assert result == {"success": True}