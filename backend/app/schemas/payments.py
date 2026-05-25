"""Payment-related Pydantic schemas."""
from app.schemas.base import AppBaseModel


class CheckoutSessionResponse(AppBaseModel):
    """Response returned after creating a Stripe Checkout Session."""

    session_url: str
