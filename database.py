# database.py
from collections.abc import Generator

from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = "postgresql://mom:@localhost:5432/url_shortener"
REDIS_URL = "redis://localhost:6379/0"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> Redis:
    return redis_client