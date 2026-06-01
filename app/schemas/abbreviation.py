from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.abbreviation import AbbreviationCraft, AbbreviationType


class AbbreviationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    abbreviation: str
    full_name: str
    description: str | None
    type: AbbreviationType
    craft: AbbreviationCraft
    video_link: str | None


class AbbreviationListResponse(BaseModel):
    abbreviations: list[AbbreviationResponse]
