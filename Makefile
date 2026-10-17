# ============================================================================
# GlucoTwin — Digital Twin Challenge 2026
# Makefile for all pipeline steps
#
# Usage:
#   make data      – Generate EHR + wearable data
#   make sample    – Generate small 50-patient sample (committed in repo)
#   make train     – Train LightGBM models
#   make eval      – Evaluate models + produce metrics.json and figures
#   make test      – Run pytest suite
#   make api       – Start the FastAPI backend
#   make demo      – Run full end-to-end demo (data → train → eval → api)
#   make clean     – Remove generated data and model artifacts
# ============================================================================

PYTHON    := python
PIP       := pip
UVICORN   := uvicorn
BACKEND   := backend
VENV_FLAG := $(if $(VIRTUAL_ENV),true,false)

.PHONY: all data sample train eval test api ui demo clean install install-ml

# ── Default ───────────────────────────────────────────────────────────────────
all: sample train eval test

# ── Install dependencies ──────────────────────────────────────────────────────
install:
	cd $(BACKEND) && $(PIP) install -r requirements.txt

install-ml:
	$(PIP) install lightgbm shap scikit-learn pandas numpy pyarrow pyyaml

# ── Data generation ───────────────────────────────────────────────────────────
data:
	$(PYTHON) data/generate_ehr.py
	$(PYTHON) data/simulate_wearable.py
	$(PYTHON) data/build_dataset.py
	@echo "[make] Full 400-patient dataset built."

sample:
	$(PYTHON) data/generate_ehr.py --sample
	$(PYTHON) data/simulate_wearable.py --sample
	$(PYTHON) data/build_dataset.py --sample
	@echo "[make] 50-patient sample built."

# ── Model training ────────────────────────────────────────────────────────────
train:
	$(PYTHON) twin/model_train.py
	@echo "[make] Models trained and saved to twin/models/"

train-sample:
	$(PYTHON) twin/model_train.py --sample

# ── Evaluation ────────────────────────────────────────────────────────────────
eval:
	$(PYTHON) twin/evaluate.py
	@echo "[make] Evaluation complete. See results/metrics.json"

eval-sample:
	$(PYTHON) twin/evaluate.py --sample

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	cd $(BACKEND) && $(PYTHON) -m pytest ../tests/ -v --tb=short 2>&1
	@echo "[make] Tests complete."

test-fast:
	cd $(BACKEND) && $(PYTHON) -m pytest ../tests/ -v --tb=short -k "not test_api" 2>&1

# ── API ───────────────────────────────────────────────────────────────────────
api:
	@echo "[make] Starting FastAPI backend on port 8000..."
	@echo "[make] Open http://localhost:8000/docs for the API explorer"
	cd $(BACKEND) && $(UVICORN) app.main:app --reload --port 8000

# ── Frontend ──────────────────────────────────────────────────────────────────
ui:
	@echo "[make] Starting frontend on port 5173..."
	@echo "[make] Open http://localhost:5173"
	cd frontend && npm run dev

# ── Full demo ─────────────────────────────────────────────────────────────────
demo: sample train-sample eval-sample
	@echo "[make] Demo pipeline complete."
	@echo "[make] Start the backend: make api"
	@echo "[make] Start the frontend: make ui"
	@echo "[make] Login at http://localhost:5173 with admin@medintel.ai / changeme123"
	@echo "[make] Navigate to GlucoTwin (T2D) in the sidebar"

# ── Database setup ────────────────────────────────────────────────────────────
db-setup:
	docker compose up -d
	@echo "Waiting for Postgres to be ready..."
	sleep 5
	cd $(BACKEND) && $(PYTHON) -m alembic upgrade head
	cd $(BACKEND) && $(PYTHON) -m app.seed
	cd $(BACKEND) && $(PYTHON) -m app.ml.train_icu_risk
	@echo "[make] Database seeded and ICU model trained."

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	@echo "[make] Removing generated data and model files..."
	-rm -f data/patients.parquet data/medications.parquet data/lab_results.parquet
	-rm -f data/patients_with_flags.parquet data/wearable.parquet data/dataset.parquet
	-rm -f twin/models/*.pkl twin/models/patient_splits.json twin/models/medians.json
	-rm -f twin_state.db
	@echo "[make] Clean done. Sample files in data/sample/ are preserved."
