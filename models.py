# models.py
from sqlalchemy import BigInteger, Column, Integer, String

from database import Base


class URLMapping(Base):
    __tablename__ = "url_mappings"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    short_code = Column(String(7), unique=True, nullable=True)
    long_url = Column(String, nullable=False)