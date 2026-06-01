from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def create(
        self, db: Session, firebase_uid: str, email: str | None, username: str
    ) -> User:
        user = User(firebase_uid=firebase_uid, email=email, username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_by_firebase_uid(self, db: Session, firebase_uid: str) -> User | None:
        return db.query(User).filter(User.firebase_uid == firebase_uid).first()

    def get_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()


user_repository = UserRepository()
