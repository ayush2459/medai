from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.routers import analytics, auth, glucotwin, ml, oauth, patients, nightscout
from app.routers.clinical_guidance import router as clinical_guidance_router

app = FastAPI(
    title="MedIntel AI",
    description="Intelligent Healthcare Analytics & Predictive Care Platform - API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Required by Authlib for the OAuth login/callback flow (stores PKCE state in a session cookie)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(patients.router)
app.include_router(analytics.router)
app.include_router(ml.router)
app.include_router(glucotwin.router)
app.include_router(clinical_guidance_router)
app.include_router(nightscout.router)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": "medintel-ai-backend"}
