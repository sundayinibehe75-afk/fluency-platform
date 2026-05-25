"""SQLAlchemy async declarative base.

All ORM models should inherit from `Base`.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass
