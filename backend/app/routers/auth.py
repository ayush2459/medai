import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token_or_raise,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest,
    TokenPair,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(User)
        .filter(User.email == payload.email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


@router.post("/login", response_model=TokenPair)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == form_data.username)
        .first()
    )

    if (
        user is None
        or not user.hashed_password
        or not verify_password(
            form_data.password,
            user.hashed_password,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    access_token = create_access_token(
        str(user.id),
        user.role.value,
    )
    refresh_token = create_refresh_token(str(user.id))

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        decoded = decode_token_or_raise(payload.refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    try:
        user_id = uuid.UUID(str(decoded.get("sub")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token subject",
        ) from exc

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(
        str(user.id),
        user.role.value,
    )
    new_refresh_token = create_refresh_token(str(user.id))

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user