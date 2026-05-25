"""JwtDenylist ORM model.

Stores revoked JWT IDs (jti claims) until they expire.
A background task prunes rows where expires_at < NOW().
"""
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JwtDenylist(Base):
    __tablename__ = "jwt_denylist"

    # jti is the primary key — VARCHAR(255) as per design
    jti: Mapped[str] = mapped_column(String(255), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<JwtDenylist jti={self.jti} expires_at={self.expires_at}>"
