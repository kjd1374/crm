from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import streamlit as st

# Check if running in Streamlit Cloud (Secrets available)
# Logic: Use PostgreSQL if 'DATABASE_URL' is in secrets, else fallback to local SQLite
try:
    if "DATABASE_URL" in st.secrets:
        DATABASE_URL = st.secrets["DATABASE_URL"]
        # SQLAlchemy requires 'postgresql://', but some providers give 'postgres://'
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    else:
        DATABASE_URL = "sqlite:///crm.db"
except FileNotFoundError:
    # Local run without secrets.toml
    DATABASE_URL = "sqlite:///crm.db"

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
