import os
import pytest

from seed import seed_database


@pytest.fixture(scope="function", autouse=True)
def setup_test_database(tmp_path, monkeypatch):

    # Create a unique temporary database for each test
    db_path = tmp_path / "test_service_agent.db"

    # Tell our application to use the test database
    monkeypatch.setenv("DB_NAME", str(db_path))

    # Create tables and insert demo data
    seed_database()

    yield