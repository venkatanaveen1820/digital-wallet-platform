
from sqlalchemy import text

from app.db.session import engine

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT current_database(), version()")
    )
    database_name, database_version = result.one()

    print("Database:", database_name)
    print("PostgreSQL:", database_version)
