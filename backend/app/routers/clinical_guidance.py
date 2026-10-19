import json, os, urllib.request, urllib.error
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["clinical-guidance"])

class GuidanceRequest(BaseModel):
    patient_id: str = Field(min_length=1, max_length=120)
    conditions: list[str] = Field(default_factory=list, max_length=30)
    prediction: dict[str, Any] = Field(default_factory=dict)
    investigations: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    patient_context: dict[str, Any] = Field(default_factory=dict)

def build_rules(req):
    tests, precautions, flags = [], [], []
    hyper = str(req.prediction.get("risk_band_hyper", "")).lower()
    hypo = str(req.prediction.get("risk_band_hypo", "")).lower()
    conditions = " ".join(req.conditions).lower()

    def add_test(name, reason):
        if not any(x["test"] == name for x in tests):
            tests.append({"test": name, "reason": reason,
                          "timing": "Clinician to determine"})

    def add_precaution(title, detail):
        if not any(x["title"] == title for x in precautions):
            precautions.append({"title": title, "detail": detail})

    if hyper == "high" or "diabetes" in conditions or "hypergly" in conditions:
        add_test("Blood glucose review", "Review current readings and symptoms with the model's risk signal.")
        add_test("HbA1c", "Consider longer-term glycaemic assessment if clinically appropriate and due.")
        add_test("eGFR and urine albumin-to-creatinine ratio", "Consider kidney screening when diabetes is established.")
        add_test("Lipid profile", "Review cardiovascular risk when appropriate.")
        add_test("Retinal/eye examination", "Consider routine diabetes eye screening if indicated and due.")
        add_test("Foot and neuropathy assessment", "Consider routine diabetes foot screening if indicated.")
        add_precaution("Glucose monitoring", "Follow the patient's prescribed monitoring and sick-day plan.")
        add_precaution("Medication safety", "Do not start, stop, or change medication based on this prototype or an AI response.")
        add_precaution("Food and activity", "Discuss individualized, sustainable food and activity choices with the care team.")
        flags.append("Very high glucose with vomiting, severe dehydration, abnormal breathing, or altered consciousness needs urgent medical assessment.")
    if hypo == "high":
        add_test("Point-of-care glucose if symptomatic", "Confirm suspected low glucose promptly under local clinical protocol.")
        add_precaution("Hypoglycaemia safety", "Follow the patient's existing clinician-provided action plan.")
        flags.append("Seizure, unconsciousness, or inability to swallow safely requires emergency assistance.")
    if not tests:
        for item in req.investigations:
            if not isinstance(item, dict):
                continue
            name = str(item.get("title") or item.get("name") or item.get("rule_id") or "Clinical investigation review")
            reason = str(item.get("message") or item.get("reason") or item.get("description") or "Discuss this existing rule result with the clinical team.")
            add_test(name, reason)
    context = req.patient_context if isinstance(req.patient_context, dict) else {}
    documented = context.get("documented_conditions", [])
    lab_results = context.get("available_results", [])

    if not isinstance(documented, list):
        documented = []
    if not isinstance(lab_results, list):
        lab_results = []

    # Use only records explicitly supplied by the patient's chart.
    for diagnosis in documented:
        if not isinstance(diagnosis, dict):
            continue
        description = str(diagnosis.get("description") or "").strip()
        if description:
            add_test(
                "Review documented diagnosis: " + description,
                "Confirm current status, symptoms, treatment history, and whether condition-specific monitoring or screening is due."
            )

    for lab in lab_results:
        if not isinstance(lab, dict) or not lab.get("is_abnormal"):
            continue
        name = str(lab.get("test_name") or "").strip()
        if not name:
            continue
        value = lab.get("value")
        unit = str(lab.get("unit") or "").strip()
        result_text = f" Recorded result: {value} {unit}.".strip() if value is not None else ""
        add_test(
            "Clinician review of abnormal result: " + name,
            "Review the recorded result, reference range, collection date, symptoms, and prior results to decide whether confirmation or follow-up is appropriate." + result_text
        )

    if not tests:
        add_test("Review clinical history and existing results", "No specific documented finding or usable glucose-risk result was available to justify a patient-specific test recommendation. The clinician should review the chart and decide which screening or follow-up, if any, is appropriate.")
    if not precautions:
        add_precaution("Clinician-led follow-up", "Review symptoms, history, medicines, allergies, and existing results before deciding on care.")
    flags += ["This is not a diagnosis or prescription. A qualified clinician must review all suggestions.",
              "Do not delay emergency care while waiting for AI guidance."]
    return {"suggested_tests": tests, "precautions": precautions,
            "red_flags": list(dict.fromkeys(flags)), "generated_by": "local_rules_fallback"}


def llm_guidance(req, fallback):
    """Try configured LLM providers; safely fall back to local rules."""
    import json
    import os
    import urllib.request
    import urllib.error

    model_prompt = (
        "Draft conservative clinician-facing decision support, not diagnosis or treatment. "
        "The supplied model predicts short-term glucose risk, not every disease. "
        "Do not infer a diagnosis solely from risk bands. Never prescribe doses or claim cure. "
        "Use only supplied information. Preserve emergency warnings. "
        "Use documented conditions and existing results to make suggestions specific. "
        "For every suggested test, explain the patient-specific reason and whether it "
        "is routine screening, follow-up of an existing finding, or symptom-driven. "
        "Do not say a condition was detected unless it is explicitly documented. "
        "Do not call a test overdue unless dates and applicable guidance support that. "
        "If relevant patient information is missing, state what the clinician should "
        "check instead of inventing findings. Do not recommend medication changes. "
        "Read patient_context.documented_conditions, available_results, and doctor_notes. "
        "Address documented abnormal laboratory results by name, value, unit, and date "
        "when supplied, and explain that the clinician should interpret them using the "
        "patient's reference range and clinical context. Do not automatically recommend "
        "repeating a test solely because it is flagged abnormal. Distinguish documented "
        "diagnoses from possible concerns. For each test suggestion, state the reason and "
        "whether it is follow-up, routine screening, or symptom-driven. "
        "Return only JSON with suggested_tests (objects test, reason, timing), "
        "precautions (objects title, detail), red_flags (strings), clinical_notes (strings)."
    )
    payload = {
        "patient_id": req.patient_id,
        "conditions": req.conditions,
        "prediction": req.prediction,
        "existing_investigations": req.investigations,
        "patient_context": req.patient_context,
        "rule_based_draft": fallback,
    }
    user_content = json.dumps(payload, default=str)

    def parse_result(content, label):
        result = json.loads(content)
        if not all(isinstance(result.get(k), list)
                   for k in ("suggested_tests", "precautions", "red_flags")):
            raise ValueError("LLM returned an invalid response structure")
        return {
            **fallback,
            **result,
            "generated_by": label,
        }

    def call_openai_compatible(base_url, api_key, model, label):
        body = json.dumps({
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": model_prompt},
                {"role": "user", "content": user_content},
            ],
        }).encode()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        request = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.loads(response.read().decode())
        content = data["choices"][0]["message"]["content"]
        return parse_result(content, label)

    def call_ollama(base_url, model):
        body = json.dumps({
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": model_prompt},
                {"role": "user", "content": user_content},
            ],
            "options": {"temperature": 0.1},
        }).encode()
        request = urllib.request.Request(
            base_url.rstrip("/") + "/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode())
        return parse_result(data["message"]["content"], "ollama:" + model)

    provider = os.getenv("CLINICAL_LLM_PROVIDER", "auto").strip().lower()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

    # Ordered failover. Explicit provider preferences are tried first.
    if provider == "ollama":
        providers = ["ollama", "groq"]
    elif provider == "groq":
        providers = ["groq", "ollama"]
    else:
        providers = ["groq", "ollama"]

    errors = []
    for name in providers:
        try:
            if name == "groq":
                if not groq_key:
                    continue
                return call_openai_compatible(
                    "https://api.groq.com/openai/v1",
                    groq_key, groq_model, "groq:" + groq_model
                )
            if name == "ollama":
                return call_ollama(ollama_url, ollama_model)
        except Exception as exc:
            # Do not expose credentials, URLs with secrets, or patient data in errors.
            errors.append(name + ":" + type(exc).__name__)

    result = dict(fallback)
    result["provider_status"] = (
        "LLM providers unavailable; local rules used"
        + (". Tried: " + ", ".join(errors) if errors else "")
    )
    return result

@router.post("/clinical-guidance")
def clinical_guidance(req: GuidanceRequest, _user: User = Depends(get_current_user)):
    result = llm_guidance(req, build_rules(req))
    return {**result, "patient_id": req.patient_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clinician_review_required": True,
        "disclaimer": "Prototype decision support only. GlucoTwin predicts short-term glucose risk, not all diseases. Verify suggestions with a qualified clinician and local guidelines."}
