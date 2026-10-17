#!/usr/bin/env python
"""
Minimal test API to verify glucotwin router works without full backend setup.
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Create minimal app with just glucotwin router
app = FastAPI(title="MedAI GlucoTwin API - Test",)

# Import router
try:
    # Temporarily mock dependencies to allow import
    from unittest.mock import MagicMock
    sys.modules['app.core.deps'] = MagicMock()
    sys.modules['app.models.user'] = MagicMock()
    
    from backend.app.routers.glucotwin import router
    app.include_router(router)
    print("✅ GlucoTwin router imported successfully")
except Exception as e:
    print(f"❌ Failed to import router: {e}")
    sys.exit(1)

# Test basic endpoints
client = TestClient(app)

print("\n=== Testing Endpoints ===")
print("\n1. Health Check:")
resp = client.get("/api/v1/health")
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")

print("\n2. List Patients (no auth expected):")
resp = client.get("/api/v1/patients")
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"   Response: {resp.json()}")
elif resp.status_code == 401:
    print("   (Auth required - expected for protected endpoint)")

print("\n✅ API structure test complete!")
