import os
import logging
from contextlib import closing
from threading import Lock
import sqlite3
from fastapi import HTTPException
from fastapi import Request
from agent import run_agent
from dotenv import load_dotenv
from anthropic import Anthropic
from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator
from tools import book_appointment
from rate_limiter import RateLimiter
from database import (
    get_connection,
    create_database,
    create_conversation,
    save_message,
    save_message_pair,
    get_conversation_messages,
    get_customer_conversations,
    conversation_belongs_to_customer,
)
from tools import (
    get_available_slots,
    get_customer_appointments,
    book_appointment,
    reschedule_appointment,
    cancel_appointment
)

logger = logging.getLogger(__name__)

# Temporary in-memory conversation storage
conversation_histories: dict[int, list[dict]] = {}
conversation_lock = Lock()

MAX_HISTORY_MESSAGES = 20

FAILED_AGENT_RESPONSES = {
    "The assistant is temporarily unavailable. Please try again later.",
    "I couldn't complete my response. Please try again.",
    "I couldn't generate a complete response. Please try again.",
    "I couldn't complete the request safely. Please try again.",
}


def is_successful_agent_response(result: dict) -> bool:
    response = result.get("response")

    return (
        isinstance(response, str)
        and bool(response.strip())
        and response not in FAILED_AGENT_RESPONSES
    )

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth import verify_access_token
from auth import authenticate_customer, create_access_token, hash_password

security = HTTPBearer()


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:

    token = credentials.credentials

    customer_id = verify_access_token(token)

    if customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM customers
            WHERE id = ?
            """,
            (customer_id,)
        )

        customer = cursor.fetchone()

    finally:
        connection.close()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer no longer exists",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return customer_id

def require_admin(
    customer_id: int = Depends(get_current_customer)
) -> int:
    """
    Verify that the authenticated customer has admin privileges.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT role
            FROM customers
            WHERE id = ?
            """,
            (customer_id,)
        )

        result = cursor.fetchone()

    finally:
        connection.close()

    if result is None or result[0] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )

    return customer_id


def require_booking_manager(
    customer_id: int = Depends(get_current_customer)
) -> int:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT role FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
    if row is None or row[0] not in ("staff", "admin"):
        raise HTTPException(403, "Staff or administrator privileges required")
    return customer_id


load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

app = FastAPI()


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError):
    if request.method == "POST" and request.url.path.rstrip("/") == "/customers":
        # Validation can attach the submitted password or the entire request body.
        errors = [
            {key: value for key, value in item.items() if key in ("loc", "msg", "type")}
            for item in error.errors()
        ]
        error = RequestValidationError(errors)
    return await request_validation_exception_handler(request, error)


# Limit each customer to 10 AI requests per minute
chat_rate_limiter = RateLimiter(
    max_requests=10,
    window_seconds=60
)

# Limit login attempts per client IP
login_rate_limiter = RateLimiter(
    max_requests=5,
    window_seconds=300
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

create_database()

class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=40)
    vehicle: str = Field(min_length=1, max_length=120)


class NewCustomer(Customer):
    email: EmailStr | None = None
    password: SecretStr | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_login(self):
        if (self.email is None) != (self.password is None):
            raise ValueError("Provide both email and password to enable login")
        return self

class Appointment(BaseModel):
    customer_id: int
    appointment_date: str
    appointment_time: str
    service_type: str


class StaffAppointment(Appointment):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: int = Field(gt=0)
    service_type: str = Field(min_length=1, max_length=120)


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_date: str
    new_time: str

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message cannot be empty")

        return value

class LoginRequest(BaseModel):
    email: str
    password: str

def delete_customer(customer_id: int):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM customers WHERE id = ?",
            (customer_id,)
        )

        deleted_rows = cursor.rowcount

        if deleted_rows == 0:
            return {
                "success": False,
                "error": "Customer not found"
            }

        connection.commit()

        return {
            "success": True,
            "deleted_customer_id": customer_id
        }

    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()
@app.get("/")
def home():
    return {"message": "AI Service Agent is running"}


@app.post("/customers")
def create_customer(
    customer: NewCustomer,
    authenticated_customer_id: int = Depends(require_admin)
):
    if not isinstance(customer, NewCustomer):
        customer = NewCustomer.model_validate(customer, from_attributes=True)
    password_hash = (
        hash_password(customer.password.get_secret_value())
        if customer.password is not None else None
    )
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO customers (name, phone, vehicle, email, password_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer.name, customer.phone, customer.vehicle, customer.email, password_hash)
        )

        customer_id = cursor.lastrowid

        connection.commit()

        return {
            "message": "Customer created",
            "customer_id": customer_id,
            "customer": customer.model_dump(exclude={"password"}, exclude_none=True)
        }

    except sqlite3.IntegrityError as error:
        connection.rollback()
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise HTTPException(409, "A customer already uses this email") from error
        raise
    except sqlite3.Error:
        connection.rollback()
        raise

    finally:
        connection.close()


@app.delete("/customers/{customer_id}")
def remove_customer(
    customer_id: int,
    authenticated_customer_id: int = Depends(get_current_customer)
):
    if customer_id != authenticated_customer_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to delete this customer."
        )

    return delete_customer(customer_id)


@app.patch("/customers/{customer_id}")
def update_customer(
    customer_id: int,
    customer: Customer,
    authenticated_customer_id: int = Depends(require_admin)
):
    with closing(get_connection()) as connection, connection:
        result = connection.execute(
            """
            UPDATE customers SET name = ?, phone = ?, vehicle = ?
            WHERE id = ? AND role = 'customer'
            """,
            (customer.name, customer.phone, customer.vehicle, customer_id),
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Customer not found")
    return {"customer_id": customer_id, "customer": customer}


@app.delete("/admin/customers/{customer_id}", status_code=204)
def admin_remove_customer(
    customer_id: int,
    authenticated_customer_id: int = Depends(require_admin)
):
    with closing(get_connection()) as connection, connection:
        result = connection.execute(
            """
            DELETE FROM customers
            WHERE id = ? AND role = 'customer'
                AND NOT EXISTS (SELECT 1 FROM appointments WHERE customer_id = customers.id)
                AND NOT EXISTS (SELECT 1 FROM conversations WHERE customer_id = customers.id)
            """,
            (customer_id,),
        )
        if result.rowcount == 0:
            exists = connection.execute(
                "SELECT 1 FROM customers WHERE id = ? AND role = 'customer'", (customer_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(404, "Customer not found")
            raise HTTPException(409, "Customers with appointments or chat history cannot be deleted")


@app.get("/customers")

def get_customers(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Get the authenticated customer's role
        cursor.execute(
            "SELECT role FROM customers WHERE id = ?",
            (authenticated_customer_id,)
        )

        result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer not found"
            )

        role = result[0]

        # Administrators can see all customers
        if role == "admin":
            cursor.execute(
                """
                SELECT id, name, phone, vehicle, email, role
                FROM customers
                ORDER BY id
                """
            )

        # Regular customers can only see themselves
        else:
            cursor.execute(
                """
                SELECT id, name, phone, vehicle
                FROM customers
                WHERE id = ?
                """,
                (authenticated_customer_id,)
            )

        rows = cursor.fetchall()

    finally:
        connection.close()

    customers = []

    for row in rows:
        customer = {
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "vehicle": row[3]
        }
        if role == "admin":
            customer.update(email=row[4], role=row[5])
        customers.append(customer)

    return {"customers": customers}

@app.post("/appointments")
def create_appointment(
    appointment: Appointment,
    authenticated_customer_id: int = Depends(get_current_customer)
):
    # Check whether the authenticated user is an administrator
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT role FROM customers WHERE id = ?",
            (authenticated_customer_id,)
        )

        result = cursor.fetchone()

    finally:
        connection.close()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer not found"
        )

    role = result[0]

    # Regular customers can only book for themselves
    if (
        appointment.customer_id != authenticated_customer_id
        and role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="You cannot create appointments for another customer."
        )

    # Book for the requested customer
    result = book_appointment(
        customer_id=appointment.customer_id,
        appointment_date=appointment.appointment_date,
        appointment_time=appointment.appointment_time,
        service_type=appointment.service_type,
        authenticated_customer_id=authenticated_customer_id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return {
        "message": "Appointment booked",
        "appointment_id": result["appointment_id"],
        "appointment": result
    }

@app.get("/appointments")


def get_appointments(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Get the authenticated customer's role
        cursor.execute(
            "SELECT role FROM customers WHERE id = ?",
            (authenticated_customer_id,)
        )

        result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Customer not found"
            )

        role = result[0]

        query = """
            SELECT
                appointments.id,
                customers.name,
                customers.vehicle,
                appointments.appointment_date,
                appointments.appointment_time,
                appointments.service_type,
                appointments.status
            FROM appointments
            JOIN customers
                ON appointments.customer_id = customers.id
        """

        # Staff and administrators can view the full booking calendar.
        if role in ("staff", "admin"):
            cursor.execute(
                query + """
                ORDER BY
                    appointments.appointment_date,
                    appointments.appointment_time
                """
            )

        # Regular customers can only view their own appointments
        else:
            cursor.execute(
                query + """
                WHERE appointments.customer_id = ?
                ORDER BY
                    appointments.appointment_date,
                    appointments.appointment_time
                """,
                (authenticated_customer_id,)
            )

        rows = cursor.fetchall()

    finally:
        connection.close()

    appointments = []

    for row in rows:
        appointments.append({
            "id": row[0],
            "customer_name": row[1],
            "vehicle": row[2],
            "date": row[3],
            "time": row[4],
            "service_type": row[5],
            "status": row[6]
        })

    return {"appointments": appointments}


@app.get("/staff/customers")
def list_booking_customers(authenticated_customer_id: int = Depends(require_booking_manager)):
    with closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT id, name FROM customers WHERE role = 'customer' ORDER BY name, id"
        ).fetchall()
    return {"customers": [{"id": customer_id, "name": name} for customer_id, name in rows]}


def get_appointment_owner(appointment_id: int) -> int:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT customer_id FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Appointment not found")
    return row[0]


def booking_manager_result(result: dict) -> dict:
    if result["success"]:
        return result
    error = result["error"]
    if error in {
        "This time slot is already booked",
        "The requested time slot is already booked",
        "Appointment not found or is not currently booked",
        "Appointment is already cancelled",
        "Appointment could not be cancelled",
    }:
        raise HTTPException(409, error)
    if error in {
        "Appointment not found",
        "Target customer does not exist",
        "Authenticated customer does not exist",
        "Invalid customer reference",
    }:
        raise HTTPException(404, error)
    if error == "Database integrity error":
        raise HTTPException(500, "Could not save the appointment")
    raise HTTPException(400, error)


@app.post("/staff/appointments", status_code=201)
def create_staff_appointment(
    appointment: StaffAppointment,
    authenticated_customer_id: int = Depends(require_booking_manager),
):
    with closing(get_connection()) as connection:
        customer = connection.execute(
            "SELECT 1 FROM customers WHERE id = ? AND role = 'customer'", (appointment.customer_id,)
        ).fetchone()
    if customer is None:
        raise HTTPException(404, "Customer not found")
    # The role dependency authorizes staff to invoke the existing customer-scoped operation.
    return booking_manager_result(book_appointment(
        **appointment.model_dump(), authenticated_customer_id=appointment.customer_id
    ))


@app.patch("/staff/appointments/{appointment_id}")
def reschedule_staff_appointment(
    appointment_id: int,
    changes: RescheduleRequest,
    authenticated_customer_id: int = Depends(require_booking_manager),
):
    owner = get_appointment_owner(appointment_id)
    return booking_manager_result(reschedule_appointment(
        appointment_id, changes.new_date, changes.new_time, authenticated_customer_id=owner
    ))


@app.post("/staff/appointments/{appointment_id}/cancel")
def cancel_staff_appointment(
    appointment_id: int,
    authenticated_customer_id: int = Depends(require_booking_manager),
):
    owner = get_appointment_owner(appointment_id)
    return booking_manager_result(cancel_appointment(appointment_id, authenticated_customer_id=owner))


@app.get("/test-claude")
def test_claude(
    authenticated_customer_id: int = Depends(require_admin)
):

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": "Say hello and confirm that the AI service agent connection works."
            }
        ]
    )

    return {
        "response": message.content[0].text
    }

@app.get("/me")
def get_me(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, name, email, role
            FROM customers
            WHERE id = ?
            """,
            (authenticated_customer_id,)
        )

        customer = cursor.fetchone()

    finally:
        connection.close()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists"
        )

    return {
        "id": customer[0],
        "name": customer[1],
        "email": customer[2],
        "role": customer[3]
    }

@app.post("/login")
def login(request: LoginRequest, http_request: Request):
    # Identify the client by its IP address.
    client_ip = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    # Check the login rate limit before verifying credentials.
    if not login_rate_limiter.allow_request(client_ip):
        retry_after = login_rate_limiter.get_retry_after(client_ip)

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    customer_id = authenticate_customer(
        email=request.email,
        password=request.password
    )

    if customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(customer_id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/chat")
def chat(
    request: ChatRequest,
    authenticated_customer_id: int = Depends(get_current_customer)
):
    # Apply the shared AI rate limit.
    if not chat_rate_limiter.allow_request(authenticated_customer_id):
        retry_after = chat_rate_limiter.get_retry_after(
            authenticated_customer_id
        )

        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    with conversation_lock:
        history = list(
            conversation_histories.get(authenticated_customer_id, [])
        )

        result = run_agent(
            message=request.message,
            authenticated_customer_id=authenticated_customer_id,
            conversation_history=list(history)
        )

        # Save only completed, successful conversations.
        if is_successful_agent_response(result):
            history.extend([
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": result["response"]},
            ])

            conversation_histories[authenticated_customer_id] = (
                history[-MAX_HISTORY_MESSAGES:]
            )

    return result

@app.delete("/chat/history")
def clear_chat_history(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    with conversation_lock:
        conversation_histories.pop(authenticated_customer_id, None)

    return {
        "success": True,
        "message": "Conversation history cleared."
    }

@app.post("/conversations", status_code=201)
def start_conversation(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    conversation_id = create_conversation(
        customer_id=authenticated_customer_id
    )

    return {
        "conversation_id": conversation_id,
        "message": "Conversation created successfully."
    }

@app.get("/conversations")
def list_conversations(
    authenticated_customer_id: int = Depends(get_current_customer)
):
    conversations = get_customer_conversations(
        customer_id=authenticated_customer_id
    )

    return {
        "conversations": conversations
    }

@app.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(
    conversation_id: int,
    authenticated_customer_id: int = Depends(get_current_customer)
):
    if not conversation_belongs_to_customer(
        conversation_id=conversation_id,
        customer_id=authenticated_customer_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

    messages = get_conversation_messages(
        conversation_id=conversation_id,
        customer_id=authenticated_customer_id
    )

    return {
        "conversation_id": conversation_id,
        "messages": messages
    }

@app.post("/conversations/{conversation_id}/chat")
def conversation_chat(
    conversation_id: int,
    request: ChatRequest,
    authenticated_customer_id: int = Depends(get_current_customer)
):
    # Verify conversation ownership before reading messages.
    if not conversation_belongs_to_customer(
        conversation_id=conversation_id,
        customer_id=authenticated_customer_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Conversation not found"
        )

        # Prevent excessive AI requests from the same customer
    if not chat_rate_limiter.allow_request(authenticated_customer_id):
        retry_after = chat_rate_limiter.get_retry_after(
            authenticated_customer_id
        )

        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    # Load the conversation history from SQLite.
    messages = get_conversation_messages(
        conversation_id=conversation_id,
        customer_id=authenticated_customer_id
    )

    # Only send the most recent messages to Claude.
    history = messages[-MAX_HISTORY_MESSAGES:]

    # Generate a response using the authenticated customer.
    try:
        result = run_agent(
            message=request.message,
            authenticated_customer_id=authenticated_customer_id,
            conversation_history=list(history)
        )

    except Exception:
        logger.exception(
            "AI agent failed for conversation %s",
            conversation_id
        )

        raise HTTPException(
            status_code=503,
            detail="The AI assistant is temporarily unavailable. Please try again later."
        ) from None

    # Save both messages only when the agent succeeds.
    # Save both messages only when the agent succeeds.
    if is_successful_agent_response(result):
        try:
            save_message_pair(
                conversation_id=conversation_id,
                user_message=request.message,
                assistant_message=result["response"]
            )

        except sqlite3.Error:
            logger.exception(
                "Database error while saving conversation %s",
                conversation_id
            )

            raise HTTPException(
                status_code=503,
                detail="Unable to save the conversation. Please try again later."
            ) from None

    return {
        **result,
        "conversation_id": conversation_id
    }
