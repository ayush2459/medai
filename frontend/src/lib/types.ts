export type UserRole = "admin" | "doctor" | "nurse" | "researcher";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  is_mfa_enabled: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DailyCount {
  day: string;
  count: number;
}

export interface WardCount {
  ward: string;
  count: number;
}

export interface DiagnosisCount {
  description: string;
  count: number;
}

export interface ExecutiveSummary {
  total_patients: number;
  currently_admitted: number;
  total_bed_capacity: number;
  occupancy_rate: number;
  new_patients_last_7_days: number;
  admissions_trend: DailyCount[];
  ward_distribution: WardCount[];
  top_diagnoses: DiagnosisCount[];
}

export interface PatientSummary {
  id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  is_admitted: boolean;
  ward: string | null;
}

export interface PatientCreate {
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: "male" | "female" | "other";
  phone?: string;
  email?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  blood_type?: string;
  allergies?: string;
}

export interface PaginatedPatients {
  total: number;
  page: number;
  page_size: number;
  items: PatientSummary[];
}

export type RiskLevel = "low" | "medium" | "high";

export interface IcuRiskResponse {
  patient_id: string;
  probability: number;
  risk_level: RiskLevel;
  top_factors: string[];
  model_note: string;
}


// GlucoTwin synthetic diabetes digital-twin API contracts.
export interface CgmReading {
  timestamp: string;
  glucose_mg_dl: number;
  [key: string]: unknown;
}

export interface GlucoPatient {
  patient_id: string;
  sex: string;
  age: number;
  bmi: number;
  diabetes_duration_years: number;
  hba1c_latest: number | null;
  insulin_flag: boolean;
  sulfonylurea_flag: boolean;
  hypertension: boolean;
  ckd_stage: number;
  genetic_risk_score: number;
}

export interface InvestigationSuggestion {
  rule_name: string;
  rule_id: string;
  rule_version: string | number;
  status: string;
  message: string;
  source_url?: string | null;
  source_name: string;
  review_status: string;
}

export interface GlucoTwinPrediction {
  p_hyper_120: number | null;
  p_hypo_120: number | null;
  risk_band_hyper: string;
  risk_band_hypo: string;
  top_factors_hyper: string[];
  top_factors_hypo: string[];
}

export interface TwinState {
  patient_id?: string;
  time_in_range_7d: number | null;
  hypo_events_14d: number | null;
  avg_sleep_h: number | null;
  steps_today: number | null;
  hrv_trend: number | null;
  confidence_flag: string;
  data_gap_flag: boolean;
  prediction?: GlucoTwinPrediction | null;
  investigations?: InvestigationSuggestion[];
  [key: string]: unknown;
}
