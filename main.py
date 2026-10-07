import os
from agent import run_agent
from dotenv import load_dotenv
from anthropic import Anthropic
from fastapi import FastAPI
from pydantic import BaseModel
from database import get_connection, create_database
from tools import (
    get_available_slots,
    get_customer_appointments,
    book_appointment,
    reschedule_appointment,
    cancel_appointment
)


load_dotenv()

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

app = FastAPI()

create_database()

class Customer(BaseModel):
    name: str
    phone: str
    vehicle: str

class Appointment(BaseModel):
    customer_id: int
    appointment_date: str
    appointment_time: str
    service_type: str

class ChatRequest(BaseModel):
    message: str

def delete_customer(customer_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM customers WHERE id = ?",
        (customer_id,)
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "deleted_customer_id": customer_id
    }

@app.get("/")
def home():
    return {"message": "AI Service Agent is running"}


@app.post("/customers")
def create_customer(customer: Customer):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO customers (name, phone, vehicle)
        VALUES (?, ?, ?)
        """,
        (customer.name, customer.phone, customer.vehicle)
    )

    connection.commit()
    customer_id = cursor.lastrowid
    connection.close()

    return {
        "message": "Customer created",
        "customer_id": customer_id,
        "customer": customer
    }

@app.delete("/customers/{customer_id}")
def remove_customer(customer_id: int):
    return delete_customer(customer_id)

@app.get("/customers")
def get_customers():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, phone, vehicle
        FROM customers
    """)

    rows = cursor.fetchall()
    connection.close()

    customers = []

    for row in rows:
        customers.append({
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "vehicle": row[3]
        })

    return {"customers": customers}

@app.post("/appointments")
def create_appointment(appointment: Appointment):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO appointments (
            customer_id,
            appointment_date,
            appointment_time,
            service_type
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            appointment.customer_id,
            appointment.appointment_date,
            appointment.appointment_time,
            appointment.service_type
        )
    )

    connection.commit()
    appointment_id = cursor.lastrowid
    connection.close()

    return {
        "message": "Appointment booked",
        "appointment_id": appointment_id,
        "appointment": appointment
    }

@app.get("/appointments")
def get_appointments():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
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
    """)

    rows = cursor.fetchall()
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

@app.get("/test-claude")
def test_claude():
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

@app.post("/chat")
def chat(request: ChatRequest):
    return run_agent(request.message)