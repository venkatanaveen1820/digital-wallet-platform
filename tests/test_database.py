
from sqlalchemy import text


def test_test_database_connection(db_session):
    result = db_session.execute(text("SELECT current_database()")).scalar_one()
    assert result == "digital_wallet_test_db"


def test_ledger_immutability_trigger_exists(db_session):
    result = db_session.execute(
        text("""
            SELECT COUNT(*)
            FROM pg_trigger
            WHERE tgrelid = 'ledger_entries'::regclass
              AND tgname = 'trg_ledger_entries_immutable'
              AND NOT tgisinternal
        """)
    ).scalar_one()

    assert result == 1
