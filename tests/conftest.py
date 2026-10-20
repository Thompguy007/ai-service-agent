import os

os.environ["DB_NAME"] = "test_service_agent.db"

import pytest
from seed import seed_database


@pytest.fixture(scope="function", autouse=True)
def setup_test_database():
    seed_database()

    yield

    if os.path.exists("test_service_agent.db"):
        os.remove("test_service_agent.db")