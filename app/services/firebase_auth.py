from firebase_admin import auth


def create_firebase_user(email: str, password: str) -> tuple[str, str | None]:
    user_record = auth.create_user(email=email, password=password)
    return user_record.uid, user_record.email
