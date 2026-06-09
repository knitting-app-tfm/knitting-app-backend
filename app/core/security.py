from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.models.user import User
from app.repositories.user import user_repository

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        decoded = verify_firebase_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    firebase_uid: str = decoded["uid"]
    user = user_repository.get_by_firebase_uid(db, firebase_uid)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user
