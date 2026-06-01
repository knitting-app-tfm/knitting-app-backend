import re

from pydantic import BaseModel, Field, field_validator

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class FirebaseRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    username: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address")
        return v.lower()
