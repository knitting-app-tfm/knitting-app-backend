from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pattern import PatternYarn, YarnWeight
from app.models.yarn import UserYarn


class YarnRepository:
    def upsert(
        self,
        db: Session,
        pattern_yarn_id: UUID,
        label: str | None,
        yarn_weight: YarnWeight | None,
        meters_per_unit: float,
        grams_per_unit: float,
        strands: int,
    ) -> UserYarn:
        yarn = (
            db.query(UserYarn)
            .filter(UserYarn.pattern_yarn_id == pattern_yarn_id)
            .first()
        )
        if yarn is None:
            yarn = UserYarn(
                pattern_yarn_id=pattern_yarn_id,
                label=label,
                yarn_weight=yarn_weight,
                meters_per_unit=meters_per_unit,
                grams_per_unit=grams_per_unit,
                strands=strands,
            )
            db.add(yarn)
        else:
            yarn.label = label
            yarn.yarn_weight = yarn_weight
            yarn.meters_per_unit = meters_per_unit
            yarn.grams_per_unit = grams_per_unit
            yarn.strands = strands
        db.commit()
        db.refresh(yarn)
        return yarn

    def get_by_pattern_yarn_id(
        self, db: Session, pattern_yarn_id: UUID
    ) -> UserYarn | None:
        return (
            db.query(UserYarn)
            .filter(UserYarn.pattern_yarn_id == pattern_yarn_id)
            .first()
        )

    def get_by_pattern_id(self, db: Session, pattern_id: UUID) -> list[UserYarn]:
        return (
            db.query(UserYarn)
            .join(PatternYarn)
            .filter(PatternYarn.pattern_id == pattern_id)
            .all()
        )


yarn_repository = YarnRepository()
