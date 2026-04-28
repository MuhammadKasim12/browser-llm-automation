"""SQLite persistence for resume generation history."""
import os
from pathlib import Path

from sqlalchemy import Column, Integer, String, Text, LargeBinary, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_db_path = os.environ.get("DATABASE_URL")
if not _db_path:
    _db_path = f"sqlite:///{Path(__file__).parent / 'resume_history.db'}"

engine = create_engine(_db_path, connect_args={"check_same_thread": False} if "sqlite" in _db_path else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Generation(Base):
    __tablename__ = "generations"
    id              = Column(Integer, primary_key=True, index=True)
    created_at      = Column(String(50), nullable=False, index=True)
    job_title       = Column(String(200), nullable=False)
    company         = Column(String(200), nullable=False)
    job_description = Column(Text, nullable=False)
    source_resume   = Column(Text, nullable=False)
    data_json       = Column(Text, nullable=False)   # final structured JSON
    pdf_blob        = Column(LargeBinary, nullable=True)
    provider        = Column(String(50), nullable=True)
    model           = Column(String(100), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
