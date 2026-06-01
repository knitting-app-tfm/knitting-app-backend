import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class CraftType(str, enum.Enum):
    KNITTING = "KNITTING"
    CROCHET = "CROCHET"


class PatternStatus(str, enum.Enum):
    IMPORTED = "IMPORTED"
    CONFIRMED = "CONFIRMED"
    TOKENIZED = "TOKENIZED"


class PatternSource(str, enum.Enum):
    PDF = "PDF"
    TEXT = "TEXT"
    RAVELRY = "RAVELRY"


class GaugeUnit(str, enum.Enum):
    CM = "CM"
    INCH = "INCH"


class YarnWeight(str, enum.Enum):
    LACE = "LACE"
    FINGERING = "FINGERING"
    DK = "DK"
    ARAN = "ARAN"
    BULKY = "BULKY"


class Pattern(Base):
    __tablename__ = "patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # nullable=True until Firebase auth is implemented
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title = Column(String, nullable=True)
    craft = Column(Enum(CraftType, name="crafttype"), nullable=True)
    status = Column(
        Enum(PatternStatus, name="patternstatus"),
        nullable=False,
        default=PatternStatus.IMPORTED,
    )
    source = Column(Enum(PatternSource, name="patternsource"), nullable=False)
    cover_image_path = Column(String, nullable=True)
    original_file_path = Column(String, nullable=False)
    parsed_json_path = Column(String, nullable=True)
    tokens_file_path = Column(String, nullable=True)
    gauge_stitches = Column(Float, nullable=True)
    gauge_rows = Column(Float, nullable=True)
    gauge_size = Column(Float, nullable=True)
    gauge_unit = Column(Enum(GaugeUnit, name="gaugeunit"), nullable=True)
    needle_size = Column(String, nullable=True)
    sizes = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    yarns = relationship(
        "PatternYarn", back_populates="pattern", cascade="all, delete-orphan"
    )


class PatternYarn(Base):
    __tablename__ = "pattern_yarns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("patterns.id"), nullable=False)
    label = Column(String, nullable=True)
    yarn_weight = Column(Enum(YarnWeight, name="yarnweight"), nullable=True)
    meters_per_unit = Column(Float, nullable=True)
    grams_per_unit = Column(Float, nullable=True)
    grams_needed = Column(Float, nullable=True)
    strands = Column(Integer, nullable=False, default=1)

    pattern = relationship("Pattern", back_populates="yarns")
