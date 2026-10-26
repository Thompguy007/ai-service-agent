import os
import logging
from dotenv import load_dotenv
from anthropic import Anthropic

from tools import (
    get_customer_appointments,
    get_available_slots,
    book_appointment,
    reschedule_appointment,
    cancel_appointment
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

appointment_tools = [
    {
        "name": "get_customer_appointments",
        "description": "Get the service appointments for a customer by their name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The customer's name, for example Mike"
                }
            },
            "required": ["customer_name"]
        }
    },
{
    "name": "book_appointment",
    "description": "Book a new service appointment for a customer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "integer",
                "description": "The ID of the customer"
            },
            "appointment_date": {
                "type": "string",
                "description": "Appointment date in YYYY-MM-DD format"
            },
            "appointment_time": {
                "type": "string",
                "description": "Appointment time in HH:MM format"
            },
            "service_type": {
                "type": "string",
                "description": "The type of service requested"
            }
        },
                "required": [
            "customer_id",
            "appointment_date",
            "appointment_time",
            "service_type"
        ]
    }
},  # ← KOMMA HER

{
    "name": "get_available_slots",
    "description": "Get the available appointment time slots for a specific date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "appointment_date": {
                "type": "string",
                "description": "The appointment date in YYYY-MM-DD format."
            }
        },
        "required": ["appointment_date"]
    }
},

{
    "name": "cancel_appointment",
    "description": "Cancel an existing service appointment using its appointment ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "appointment_id": {
                "type": "integer",
                "description": "The unique ID of the appointment to cancel."
            }
        },
        "required": ["appointment_id"]
    }
},

{
    "name": "reschedule_appointment",
    "description": "Reschedule an existing booked service appointment to a new date and time.",
    "input_schema": {
        "type": "object",
        "properties": {
            "appointment_id": {
                "type": "integer",
                "description": "The unique ID of the appointment to reschedule."
            },
            "new_date": {
                "type": "string",
                "description": "The new appointment date in YYYY-MM-DD format."
            },
            "new_time": {
                "type": "string",
                "description": "The new appointment time in HH:MM format."
            }
        },
        "required": [
            "appointment_id",
            "new_date",
            "new_time"
        ]
    }
}

]  # ← lukker appointment_tools-listen

def run_agent(message: str):

    messages = [
        {
            "role": "user",
            "content": message
        }

    ]

    for step in range(5):
    
            logger.info("Agent step %s started", step + 1)
    
            response = client.messages.create(
                model="claude-sonnet-5",
                system="""
            You are a service appointment assistant.
    
            Only offer actions that can actually be performed using the tools provided to you.
            Never claim that you can change, cancel, or modify an existing appointment unless you have a tool that supports that action.
            If a requested action cannot be performed with the available tools, explain that clearly to the customer.
            """,
                max_tokens=500,
                tools=appointment_tools,
                messages=messages
            )
    
            logger.info("Claude stop reason: %s", response.stop_reason)
    
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(
                        "tool called: %s | input=%s",
                        block.name,
                        block.input
                    )
    
            # Hvis Claude ikke vil bruge et tool,
            # har vi det endelige svar
            if response.stop_reason != "tool_use":
                text_blocks = [
                    block.text
                    for block in response.content
                    if block.type == "text"
                ]
    
                return {
                    "response": "\n".join(text_blocks)
                }
    
            # Gem Claudes tool requests i samtalen
            messages.append({
                "role": "assistant",
                "content": response.content
            })
    
            # Find ALLE tools Claude vil bruge
            tool_uses = [
                block
                for block in response.content
                if block.type == "tool_use"
            ]
    
            tool_results = []
    
            # Kør ALLE tools
            for tool_use in tool_uses:
                try:
                    if tool_use.name == "get_customer_appointments":
                        tool_result = get_customer_appointments(
                            tool_use.input["customer_name"]
                            )
        
                    elif tool_use.name == "book_appointment":
                        tool_result = book_appointment(
                            customer_id=tool_use.input["customer_id"],
                            appointment_date=tool_use.input["appointment_date"],
                            appointment_time=tool_use.input["appointment_time"],
                            service_type=tool_use.input["service_type"]
                        )
        
                    elif tool_use.name == "get_available_slots":
                        tool_result = get_available_slots(
                            tool_use.input["appointment_date"]
                        )
        
                    elif tool_use.name == "cancel_appointment":
                        tool_result = cancel_appointment(
                            tool_use.input["appointment_id"]
            )
        
                    elif tool_use.name == "reschedule_appointment":
                        tool_result = reschedule_appointment(
                            appointment_id=tool_use.input["appointment_id"],
                            new_date=tool_use.input["new_date"],
                            new_time=tool_use.input["new_time"]
            )
                    # Hvis Claude forsøger at kalde et tool, som hvores agent ikke kender/tillader, udfører vi ingenting, og sender en kontrolleret fejl tilbage.
                    else:
                        tool_result = {
                            "success": False,
                            "error": "Unknown tool"
                        }
                except KeyError as error:
                    tool_result = {
                        "success": False,
                        "error": f"Missing required tool argument: {error.args[0]}"
                }
                logger.info(
                    "Tool completed: %s | result=%s",
                    tool_use.name,
                    tool_result
)
                # Gem resultatet fra DETTE tool
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": str(tool_result)
                })
    
            # Send ALLE tool-resultater tilbage til Claude
            messages.append({
                "role": "user",
                "content": tool_results
            })
    
    return {
            "response": "I couldn't complete the request safely. Please try again."
        }

