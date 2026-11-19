import pytest
from main import conversation_histories, conversation_lock
from auth import create_access_token
from tests.test_seed import seed_test_database


@pytest.fixture(scope="function", autouse=True)
def setup_test_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test_service_agent.db"

    monkeypatch.setenv("DB_NAME", str(db_path))

    seed_test_database()

    # Clear conversation history before each test.
    with conversation_lock:
        conversation_histories.clear()

    yield

    # Clear conversation history after each test.
    with conversation_lock:
        conversation_histories.clear()


@pytest.fixture
def auth_headers():
    """
    Return authentication headers for demo customer ID 1.
    """
    token = create_access_token(customer_id=1)

    return {
        "Authorization": f"Bearer {token}"
    }