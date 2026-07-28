# models.py
from sqlalchemy import Column, BigInteger, String, DateTime, Sequence
from sqlalchemy.sql import func
from database import Base

# Define the sequence explicitly for PostgreSQL
url_id_seq = Sequence('url_id_seq', start=62**6)


class URLMapping(Base):
    __tablename__ = "url_mappings"

    # Pass the sequence to the column constructor
    id = Column(
        BigInteger, 
        url_id_seq,
        primary_key=True
    )
    short_code = Column(String(7), unique=True, index=True, nullable=True)
    long_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
