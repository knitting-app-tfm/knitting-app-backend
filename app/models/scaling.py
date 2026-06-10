import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserScaling(Base):
    __tablename__ = "user_scalings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_id = Column(
        UUID(as_uuid=True), ForeignKey("patterns.id"), nullable=False, unique=True
    )
    size_label = Column(String, nullable=False)
    size_position = Column(Integer, nullable=False)

    pattern = relationship("Pattern", back_populates="scaling")
