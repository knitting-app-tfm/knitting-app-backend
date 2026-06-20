from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import FirebaseRegisterRequest
from app.schemas.user import RegisterRequest, UserResponse
from app.services.ravelry import ravelry_service
from app.services.ravelry.ravelry_exceptions import RavelryAuthError
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


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user",
    description="Returns the current user's profile. Used by the frontend on startup to verify the session.",
)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


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


@router.get(
    "/ravelry/login",
    summary="Initiate Ravelry OAuth 2.0 login",
    description="Redirects the browser to Ravelry's authorization page.",
)
def ravelry_login() -> RedirectResponse:
    return RedirectResponse(url=ravelry_service.build_authorize_url())


@router.get(
    "/ravelry/callback",
    summary="Ravelry OAuth 2.0 callback",
    description="Exchanges the authorization code for a Firebase custom token and redirects to the frontend.",
)
def ravelry_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _error_redirect = f"{settings.FRONTEND_BASE_URL}/login?error=ravelry_failed"

    if error or not state or not ravelry_service.verify_state(state) or not code:
        return RedirectResponse(url=_error_redirect)

    try:
        access_token = ravelry_service.exchange_code_for_token(code)
        ravelry_username = ravelry_service.get_ravelry_username(access_token)
        user = ravelry_service.login_or_create_user(db, ravelry_username, access_token)
        firebase_token = ravelry_service.create_firebase_custom_token(user.firebase_uid)
    except (RavelryAuthError, Exception):
        return RedirectResponse(url=_error_redirect)

    return RedirectResponse(
        url=f"{settings.FRONTEND_BASE_URL}/ravelry/complete?token={firebase_token}"
    )
