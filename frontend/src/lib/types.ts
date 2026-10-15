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
