from database import SessionLocal, engine
from sqlalchemy import text

def migrate():
    with SessionLocal() as db:
        print("Migrating quote_items table...")
        
        # List of new columns and their types
        new_columns = [
            ("print_type", "VARCHAR"),
            ("origin", "VARCHAR"),
            ("color", "VARCHAR"),
            ("cutting", "BOOLEAN DEFAULT 0"),
            ("remote_control", "BOOLEAN DEFAULT 0"),
            ("due_date", "VARCHAR"),
            ("note", "VARCHAR")
        ]
        
        # Check if columns exist (simple try-except or just attempt add)
        # SQLite supports ADD COLUMN. PostgreSQL does too.
        # We will attempt to add them one by one.
        
        for col, dtype in new_columns:
            try:
                sql = f"ALTER TABLE quote_items ADD COLUMN {col} {dtype}"
                db.execute(text(sql))
                print(f"Added column: {col}")
            except Exception as e:
                print(f"Skipping {col} (maybe exists): {e}")
                
        db.commit()
        print("Migration done.")

if __name__ == "__main__":
    migrate()
