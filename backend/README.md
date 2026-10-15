# MedIntel AI Backend

FastAPI backend for authentication, patient records, analytics, and ICU-risk inference.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Configure your database and secret values locally before running. Do not commit `.env` or real patient information.