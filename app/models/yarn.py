import uuid

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.pattern import YarnWeight


class UserYarn(Base):
    __tablename__ = "user_yarns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_yarn_id = Column(
        UUID(as_uuid=True), ForeignKey("pattern_yarns.id"), nullable=False
    )
    label = Column(String, nullable=True)
    yarn_weight = Column(Enum(YarnWeight, name="yarnweight"), nullable=True)
    meters_per_unit = Column(Float, nullable=True)
    grams_per_unit = Column(Float, nullable=True)
    strands = Column(Integer, nullable=False, default=1)

    calculated_grams_needed = Column(Float, nullable=True)
    calculated_skeins_needed = Column(Integer, nullable=True)

    pattern_yarn = relationship("PatternYarn", back_populates="user_yarn")
