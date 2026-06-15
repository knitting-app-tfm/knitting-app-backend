import uuid

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.pattern import GaugeUnit


class UserScaling(Base):
    __tablename__ = "user_scalings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_id = Column(
        UUID(as_uuid=True), ForeignKey("patterns.id"), nullable=False, unique=True
    )
    size_label = Column(String, nullable=False)
    size_position = Column(Integer, nullable=False)
    gauge_stitches = Column(Float, nullable=False)
    gauge_rows = Column(Float, nullable=True)
    gauge_size = Column(Float, nullable=False)
    gauge_unit = Column(Enum(GaugeUnit, name="gaugeunit"), nullable=False)
    needle_size = Column(String, nullable=True)

    pattern = relationship("Pattern", back_populates="scaling")
