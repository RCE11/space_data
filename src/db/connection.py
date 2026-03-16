import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get("SUPABASE_DATABASE_URL") or os.environ["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c statement_timeout=120000"},  # 120s timeout
)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
