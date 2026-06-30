export type Tab =
  | "account"
  | "search"
  | "opportunityDetail"
  | "opportunities"
  | "tracker"
  | "documents"
  | "uploads"
  | "notifications"
  | "admin";

export type StudentProfile = {
  full_name: string | null;
  country: string | null;
  degree: string | null;
  field: string | null;
  semester: string | null;
  cgpa: number | null;
  skills: string[];
  preferred_countries: string[];
  preferred_regions: string[];
  preferred_opportunity_types: string[];
  budget_preference: string | null;
  ielts_status: string | null;
  gre_status: string | null;
  career_goal: string | null;
};

export type Notice = { kind: "success" | "error"; message: string } | null;

export type SearchJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  current_stage?: string;
  progress_message?: string;
  result?: SearchResultPayload;
  error?: string;
  query?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
};

export type SearchResultPayload = {
  answer?: string;
  queries?: string[];
  opportunities?: OpportunityRecord[];
  errors?: string[];
  raw_result_count?: number;
  candidate_count?: number;
  extracted_count?: number;
  deduplicated_count?: number;
  ranked_count?: number;
};

export type OpportunityRecord = {
  id?: string;
  saved_id?: string;
  saved_at?: string;
  title?: string;
  provider?: string | null;
  country?: string | null;
  opportunity_type?: string | null;
  deadline?: string | null;
  funding_type?: string | null;
  summary?: string | null;
  application_url?: string | null;
  contact_email?: string | null;
  priority?: string | null;
  priority_score?: number | null;
  source_tier?: string | null;
  eligibility?: string[];
  required_documents?: string[];
  warnings?: string[];
  extraction_notes?: string[];
  payment_requested?: boolean;
  verification?: {
    trust_level?: string;
    source_tier?: string;
    domain?: string;
    notes?: string[];
    risk_flags?: string[];
    deadline_verification?: {
      deadline?: string | null;
      deadline_type?: string;
      applies_to?: string;
      source_url?: string | null;
      source_text?: string;
      confidence?: number;
      confidence_label?: string;
      source_type?: string;
      status?: string;
      note?: string;
      last_checked?: string;
    };
  };
  eligibility_result?: {
    eligible?: boolean;
    score?: number;
    reasons?: string[];
    missing_requirements?: string[];
    deadline_passed?: boolean;
  };
};

export type UploadedFileRecord = {
  id: string;
  purpose?: string | null;
  path?: string | null;
  original_filename?: string | null;
  mime_type?: string | null;
  extracted_text?: string | null;
  extracted_json?: unknown;
  created_at?: string;
};

export type GeneratedDocumentRecord = {
  id: string;
  document_type?: string | null;
  content?: string | null;
  grounding_flags?: string[] | null;
  parent_document_id?: string | null;
  source_upload_id?: string | null;
  version_number?: number | null;
  regeneration_instruction?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type ApplicationTaskRecord = {
  id: string;
  internal_id?: string | null;
  task_code?: string | null;
  title?: string | null;
  status?: string | null;
  due_date?: string | null;
  opportunity_id?: string | null;
  opportunity?: {
    public_code?: string | null;
    title?: string | null;
    provider?: string | null;
    deadline?: string | null;
  } | null;
  email_status?: {
    sent?: boolean;
    status?: "sent" | "not_sent" | string;
    sent_count?: number;
    sent_at?: string | null;
    notification_email?: string | null;
    reminder_date?: string | null;
  } | null;
  next_task?: string | null;
  notes?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type LoadingKey =
  | "auth"
  | "workspace"
  | "profile"
  | "search"
  | "opportunities"
  | "tracker"
  | "documents"
  | "uploadPoster"
  | "uploadDocument"
  | "notifications"
  | "admin";

export type AdminHealth = {
  providers?: Record<string, { calls?: number; failures?: number; avg_latency_ms?: number }>;
  recent_jobs?: Array<{ id: string; status?: string; progress_message?: string; error?: string }>;
};

export type EvalRunRecord = {
  id: string;
  model_name?: string | null;
  extraction_accuracy?: number | null;
  hallucination_rate?: number | null;
  notes?: string | null;
  created_at?: string | null;
};
