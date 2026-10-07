# AI Service Agent

A conversational AI service-booking agent built with FastAPI, Claude, and SQLite.

The agent understands natural-language customer requests and can use tools to interact with a real backend. It can retrieve appointments, check availability, create bookings, reschedule appointments, and cancel appointments.

## Why I Built This

I built this project to explore how LLM-based agents can move beyond generating text and safely perform actions in a real application.

The project focuses on:

- LLM tool/function calling
- Multi-step agent workflows
- Backend guardrails
- API and database integration
- Error handling and debugging
- Automated testing of agent behavior

## Architecture

```text
Client
  |
  v
FastAPI
(main.py)
  |
  v
AI Agent
(agent.py)
  |
  |-- Claude API
  |-- Tool selection
  |-- Multi-step agent loop
  |
  v
Agent Tools
(tools.py)
  |
  |-- Get customer appointments
  |-- Check available time slots
  |-- Book appointment
  |-- Reschedule appointment
  |-- Cancel appointment
  |
  v
Database Layer
(database.py)
  |
  v
SQLite


## Safety and Guardrails

The LLM does not directly modify the database.

Claude decides which tool to call, but the Python backend validates and performs the actual operation. This keeps important business rules outside the language model.

Examples:

- A time slot cannot be double-booked.
- An appointment cannot be rescheduled to an occupied time slot.
- Availability is calculated from the database rather than invented by the LLM.
- Unknown tool calls are rejected.
- The agent has a maximum number of execution steps and returns a safe fallback if it cannot complete the request.

This means the backend remains the source of truth even when the LLM makes decisions about which actions to perform.

## Testing

The project includes automated tests for both backend rules and end-to-end agent behavior.

Current test coverage includes:

- Available and unavailable appointment slots
- Double-booking prevention
- Rescheduling conflict prevention
- Chat endpoint behavior
- Retrieval of real customer appointments
- Unknown-customer behavior
- Verification that the agent does not create a second booking in an occupied slot

Run the test suite with:

```bash
pytest -v
```

Current result:

```text
7 passed
```


## Tech Stack

- Python
- FastAPI
- Anthropic Claude API
- SQLite
- Pytest
- Pydantic

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd ai-service-agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Claude API key

Copy `.env.example` to `.env` and add your Anthropic API key:

```text
ANTHROPIC_API_KEY=your_api_key_here
```

Never commit the `.env` file.

### 5. Start the API

```bash
fastapi dev main.py
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Example

A customer can send a natural-language request such as:

```text
Hi, I'm Mike. What appointments do I have?
```

The agent can determine that appointment data is required, call the appropriate backend tool, retrieve the data from SQLite, and use the result to generate its response.

For requests that modify data, the backend validates the operation before changing the database.