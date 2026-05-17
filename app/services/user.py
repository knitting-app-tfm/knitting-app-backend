from firebase_admin.auth import (
    EmailAlreadyExistsError as FirebaseEmailAlreadyExistsError,
)
from sqlalchemy.orm import Session

from app.core.firebase import verify_firebase_token
from app.models.user import User
from app.repositories.user import user_repository
from app.services.firebase_auth import create_firebase_user


class UserAlreadyExistsError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


class UserService:
    def register(self, db: Session, firebase_token: str, username: str) -> User:
        decoded = verify_firebase_token(firebase_token)
        firebase_uid: str = decoded["uid"]
        email: str | None = decoded.get("email")

        if user_repository.get_by_firebase_uid(db, firebase_uid) is not None:
            raise UserAlreadyExistsError(
                f"User with firebase_uid {firebase_uid} already exists"
            )

        if user_repository.get_by_username(db, username) is not None:
            raise UsernameTakenError(f"Username '{username}' is already taken")

        return user_repository.create(
            db, firebase_uid=firebase_uid, email=email, username=username
        )

    def register_with_credentials(
        self, db: Session, email: str, password: str, username: str
    ) -> User:
        if user_repository.get_by_username(db, username) is not None:
            raise UsernameTakenError(f"Username '{username}' is already taken")

        try:
            firebase_uid, firebase_email = create_firebase_user(email, password)
        except FirebaseEmailAlreadyExistsError:
            raise UserAlreadyExistsError(f"User with email {email} already exists")

        return user_repository.create(
            db, firebase_uid=firebase_uid, email=firebase_email, username=username
        )


user_service = UserService()
