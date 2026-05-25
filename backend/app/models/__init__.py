"""SQLAlchemy ORM models.

All models are imported here so that Alembic's env.py can discover them
via `from app.models import *` or `import app.models`.
"""
from app.models.availability_slot import AvailabilitySlot
from app.models.booking import Booking
from app.models.jwt_denylist import JwtDenylist
from app.models.message import Message
from app.models.password_reset_token import PasswordResetToken
from app.models.payment import Payment
from app.models.price_config import PriceConfig
from app.models.review import Review
from app.models.tutor import Tutor
from app.models.user import User

__all__ = [
    "AvailabilitySlot",
    "Booking",
    "JwtDenylist",
    "Message",
    "PasswordResetToken",
    "Payment",
    "PriceConfig",
    "Review",
    "Tutor",
    "User",
]
