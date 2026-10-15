from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenPair

router = APIRouter(prefix="/api/auth/oauth", tags=["oauth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.OAUTH_GOOGLE_CLIENT_ID,
    client_secret=settings.OAUTH_GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def oauth_login(request: Request):
    if not settings.OAUTH_GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured. Set OAUTH_GOOGLE_CLIENT_ID/SECRET in .env",
        )
    redirect_uri = settings.OAUTH_REDIRECT_URL
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", response_model=TokenPair)
async def oauth_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google did not return an email")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            full_name=userinfo.get("name", email.split("@")[0]),
            hashed_password=None,
            role=UserRole.DOCTOR,
            oauth_provider="google",
            oauth_subject=userinfo.get("sub"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))
    return TokenPair(access_token=access_token, refresh_token=refresh_token)
