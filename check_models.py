
from app.db.base import Base
from app.models import Role, User, UserRole

print("Registered tables:")
for table_name in sorted(Base.metadata.tables):
    print("-", table_name)
