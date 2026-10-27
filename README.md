# AI Service Agent

A conversational AI service-booking agent built with FastAPI, Claude, and SQLite.

The agent understands natural-language customer requests and can use backend tools to retrieve appointments, check availability, create bookings, reschedule appointments, and cancel appointments.

## Why I Built This

I built this project to explore how LLM-based agents can move beyond generating text and safely perform actions in a real application.

The project focuses on:

* LLM tool/function calling
* Multi-step agent workflows
* Safe tool execution
* Backend guardrails
* API and database integration
* Error handling and debugging
* Automated testing and agent evaluation
* Structured logging and observability
* CI with GitHub Actions

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
  |-- Multi-step agent loop
  |-- Tool selection
  |-- Tool registry / dispatcher
  |-- Tool execution guardrails
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
```

Claude decides which tool should be used, while the Python agent controls which tools are actually available and dispatches approved tool calls through a tool registry.

This keeps orchestration separate from the implementation of individual tools and makes it easier to add additional tools without expanding a large `if/elif` routing chain.

## Safety and Guardrails

The LLM does not directly modify the database.

Claude can request actions through tools, but the Python backend validates and performs the actual operation. Important business rules therefore remain outside the language model.

Examples:

* A time slot cannot be double-booked. This is enforced both by application-level validation and a database-level unique constraint for active bookings.
* An appointment cannot be rescheduled to an occupied time slot.
* Appointment dates and times are validated by the backend.
* Bookings are restricted to supported appointment time slots.
* Availability is calculated from the database rather than invented by the LLM.
* Unknown tool calls are rejected safely.
* Invalid or missing tool arguments are handled without crashing the agent.
* Tool execution is restricted to functions registered by the backend.
* The agent has a maximum number of execution steps and returns a safe fallback if it cannot complete the request.

The backend therefore remains the source of truth even when the LLM decides which actions should be attempted.

## Testing and Evaluation

The project separates deterministic backend/agent tests from evaluations that use the real Claude API.

### Deterministic tests

The default test suite does not require an Anthropic API call and covers areas such as:

* Available and unavailable appointment slots
* Double-booking prevention
* Database-level booking constraints
* Rescheduling conflict prevention
* Date and time validation
* Allowed appointment time slots
* Mocked agent responses
* Mocked tool execution
* Unknown tool calls
* Missing or invalid tool arguments
* Isolated database state between tests

Run the deterministic test suite with:

```bash
pytest -v
```

Current result:

```text
12 passed, 8 deselected
```

### Claude evaluations

A separate evaluation suite tests the behavior of the agent using the real Claude API.

These scenarios include:

* Retrieval of existing customer appointments
* Paraphrased natural-language requests
* Requests with missing information
* Occupied booking slots
* Appointment rescheduling
* Chat endpoint behavior
* Unknown-customer behavior
* Safe handling of booking conflicts

Run the live Claude evaluations with:

```bash
pytest -m eval -v
```

The project currently contains **20 tests in total: 12 deterministic tests and 8 live-Claude evaluation tests.**

## Continuous Integration

GitHub Actions automatically runs the deterministic test suite on pushes and pull requests.

The CI pipeline:

1. Checks out the repository
2. Sets up Python 3.12
3. Installs project dependencies
4. Runs `pytest -v`

Live Claude evaluations are excluded from the default CI suite so that automated tests remain deterministic and do not require an API key.

## Tech Stack

* Python
* FastAPI
* Anthropic Claude API
* SQLite
* Pytest
* Pydantic
* GitHub Actions

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Thompguy007/ai-service-agent.git
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

### 5. Seed the demo database

Create the demo customers and appointments:

```bash
python seed.py
```

### 6. Start the API

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

The agent determines that appointment data is required, selects the appropriate tool, and the tool registry dispatches the request to the corresponding Python function.

The tool retrieves the data from SQLite and returns the result to the agent, which uses it to generate a natural-language response.

For requests that modify data, the backend validates the operation before changing the database.
