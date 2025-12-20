from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import streamlit as st

# FORCE TEST DB
DATABASE_URL = "sqlite:///crm_test_v2.db"

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
