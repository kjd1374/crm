from database import get_db
import utils

db = next(get_db())
print("Resetting database...")
if utils.reset_database(db):
    print("Database cleared.")
else:
    print("Failed to clear database.")
db.close()
