from __future__ import annotations
import hashlib, os
from datetime import datetime, timezone
from typing import Any
import httpx
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.deps import get_current_user
from app.models.user import User
from app.routers import glucotwin as gt

# Pydantic settings do not necessarily populate os.environ, so load backend/.env explicitly.
load_dotenv(dotenv_path=__import__('pathlib').Path(__file__).resolve().parents[2] / '.env', override=False)

router = APIRouter(prefix="/api/v1/integrations/nightscout", tags=["live CGM integration"])

class SyncRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=100)

def _config():
    return (
        os.getenv("NIGHTSCOUT_URL", "").strip().rstrip("/"),
        os.getenv("NIGHTSCOUT_TOKEN", "").strip() or None,
        os.getenv("NIGHTSCOUT_API_SECRET", "").strip() or None,
        os.getenv("NIGHTSCOUT_PATIENT_ID", "").strip() or None,
    )

@router.get("/status")
def integration_status(_current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    url, token, api_secret, patient_id = _config()
    configured = bool(url and (token or api_secret) and patient_id)
    return {
        "provider": "Nightscout", "configured": configured,
        "patient_mapping_configured": bool(patient_id),
        "authentication_configured": bool(token or api_secret),
        "poll_interval_seconds": 30, "mode": "read-only pull",
        "message": "Nightscout configured." if configured else
        "Not configured. Set NIGHTSCOUT_URL, NIGHTSCOUT_TOKEN (read-only token recommended), and NIGHTSCOUT_PATIENT_ID in backend/.env."
    }

@router.post("/sync")
async def sync_nightscout(payload: SyncRequest, _current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    url, token, api_secret, configured_patient_id = _config()
    if not url or not (token or api_secret) or not configured_patient_id:
        raise HTTPException(status_code=503, detail="Nightscout is not configured. Set NIGHTSCOUT_URL, NIGHTSCOUT_TOKEN, and NIGHTSCOUT_PATIENT_ID in backend/.env.")
    if payload.patient_id != configured_patient_id:
        raise HTTPException(status_code=403, detail="Selected patient does not match NIGHTSCOUT_PATIENT_ID. Configure a separate authorized mapping for each patient.")

    gt._load_patients()
    if payload.patient_id not in gt._PATIENT_CACHE:
        raise HTTPException(status_code=404, detail=f"Patient {payload.patient_id} has no EHR profile in GlucoTwin. Create the patient profile first via POST /api/v1/ehr/patients; do not map live readings to a synthetic cohort record.")

    headers = {"Accept": "application/json"}
    params: dict[str, str | int] = {"count": 100}
    if token:
        params["token"] = token
    elif api_secret:
        headers["api-secret"] = hashlib.sha1(api_secret.encode("utf-8")).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(f"{url}/api/v1/entries/sgv.json", params=params, headers=headers)
            response.raise_for_status()
            entries = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Timed out connecting to Nightscout.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Nightscout returned HTTP {exc.response.status_code}. Check URL and read-only token.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not read Nightscout response: {exc}") from exc

    if not isinstance(entries, list):
        raise HTTPException(status_code=502, detail="Nightscout response was not a JSON entries list.")

    rows = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            glucose = float(item.get("sgv"))
            if not 20 <= glucose <= 600:
                continue
            raw_ts = item.get("dateString")
            if raw_ts:
                timestamp = pd.Timestamp(raw_ts).to_pydatetime()
            elif item.get("date") is not None:
                timestamp = datetime.fromtimestamp(float(item["date"]) / 1000, tz=timezone.utc)
            else:
                continue
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            rows.append({"patient_id": payload.patient_id, "timestamp": timestamp,
                         "glucose_mg_dl": glucose, "heart_rate": None, "hrv_rmssd": None,
                         "steps": 0.0, "sleep_stage": 0, "sensor_quality_flag": 1})
        except (TypeError, ValueError, OverflowError):
            continue

    if not rows:
        return {"provider": "Nightscout", "patient_id": payload.patient_id, "received": 0,
                "new_readings": 0, "latest_reading_at": None,
                "message": "Connected, but no valid glucose entries were returned."}

    incoming = pd.DataFrame(rows)
    incoming["timestamp"] = pd.to_datetime(incoming["timestamp"], utc=True)
    existing = gt._WEARABLE_CACHE.get(payload.patient_id, pd.DataFrame())
    if not existing.empty:
        existing = existing.copy()
        existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
    before = set(existing["timestamp"].astype(str).tolist()) if not existing.empty else set()
    merged = pd.concat([existing, incoming], ignore_index=True)
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
    merged = merged.drop_duplicates(subset=["patient_id", "timestamp"], keep="last").sort_values("timestamp").tail(2016).reset_index(drop=True)
    new_count = sum(str(ts) not in before for ts in incoming["timestamp"].astype(str).tolist())
    gt._WEARABLE_CACHE[payload.patient_id] = merged
    try:
        from twin.state import update_twin_state
        update_twin_state(payload.patient_id, merged, db_path=gt.TWIN_DB)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Readings received but twin state update failed: {exc}") from exc
    latest = merged.iloc[-1]["timestamp"]
    return {"provider": "Nightscout", "patient_id": payload.patient_id, "received": len(rows),
            "new_readings": int(new_count), "latest_reading_at": pd.Timestamp(latest).isoformat(),
            "message": "Read-only CGM sync completed. Prediction refreshes on the next twin request."}
