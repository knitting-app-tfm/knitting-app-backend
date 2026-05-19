import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class AbbreviationType(str, enum.Enum):
    STITCH = "STITCH"
    DECREASE = "DECREASE"
    INCREASE = "INCREASE"
    TECHNIQUE = "TECHNIQUE"
    CONSTRUCTION = "CONSTRUCTION"
    YARN_HANDLING = "YARN_HANDLING"
    MARKER = "MARKER"
    PATTERN_STRUCTURE = "PATTERN_STRUCTURE"
    OTHER = "OTHER"


class AbbreviationCraft(str, enum.Enum):
    KNITTING = "KNITTING"
    CROCHET = "CROCHET"


class Abbreviation(Base):
    __tablename__ = "abbreviations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    abbreviation = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(Enum(AbbreviationType, name="abbreviationtype"), nullable=False)
    craft = Column(Enum(AbbreviationCraft, name="abbreviationcraft"), nullable=False)
    video_link = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
