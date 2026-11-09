"""Student profile: level, goal and time zone."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.timefmt import is_valid_timezone
from app.schemas.auth import LearningGoal


class ProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    cefr_level: Optional[str] = None
    timezone: str
    learning_goal: Optional[str] = None
    goal_note: Optional[str] = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    cefr_level: Optional[Literal["A0", "A1", "A2", "B1", "B2", "C1", "C2"]] = None
    timezone: Optional[str] = None
    learning_goal: Optional[LearningGoal] = None
    goal_note: Optional[str] = Field(None, max_length=500)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value):
        if value is not None and not is_valid_timezone(value):
            raise ValueError("Unknown time zone")
        return value
