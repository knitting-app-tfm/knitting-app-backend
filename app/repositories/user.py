from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def create(
        self,
        db: Session,
        firebase_uid: str,
        email: str | None,
        username: str,
        ravelry_username: str | None = None,
        ravelry_token: str | None = None,
    ) -> User:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            username=username,
            ravelry_username=ravelry_username,
            ravelry_token=ravelry_token,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_by_firebase_uid(self, db: Session, firebase_uid: str) -> User | None:
        return db.query(User).filter(User.firebase_uid == firebase_uid).first()

    def get_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()

    def get_by_ravelry_username(
        self, db: Session, ravelry_username: str
    ) -> User | None:
        return db.query(User).filter(User.ravelry_username == ravelry_username).first()


user_repository = UserRepository()
