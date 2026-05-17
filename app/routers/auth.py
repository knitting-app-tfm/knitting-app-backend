from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import FirebaseRegisterRequest
from app.schemas.user import RegisterRequest, UserResponse
from app.services.user import UserAlreadyExistsError, UsernameTakenError, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/firebase/register",
    response_model=UserResponse,
    status_code=201,
    summary="[Dev] Full registration in one step",
    description=(
        "**For Swagger testing only.** Creates a user in Firebase Authentication and registers them in the database in a single request. "
        "Equivalent to the full frontend registration flow."
    ),
)
def firebase_register(
    body: FirebaseRegisterRequest, db: Session = Depends(get_db)
) -> UserResponse:
    try:
        user = user_service.register_with_credentials(
            db, body.email, body.password, body.username
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except UsernameTakenError:
        raise HTTPException(status_code=409, detail="Username already taken")
    return UserResponse.model_validate(user)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register user in the database (step 2 of registration)",
    description=("Verifies a Firebase token and creates the user in the database. "),
)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    try:
        user = user_service.register(db, body.firebase_token, body.username)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except UsernameTakenError:
        raise HTTPException(status_code=409, detail="Username already taken")
    return UserResponse.model_validate(user)
