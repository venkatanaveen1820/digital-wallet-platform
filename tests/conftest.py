
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def test_engine():
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("TEST_DATABASE_URL must be set before running tests.")

    url = make_url(database_url)

    if url.database != "digital_wallet_test_db":
        pytest.fail("Tests may only use digital_wallet_test_db.")

    if url.host not in {"localhost", "127.0.0.1"}:
        pytest.fail("Tests may only use the local test database.")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception:
        engine.dispose()
        raise

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
