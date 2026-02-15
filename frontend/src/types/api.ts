/**
 * API type definitions for the Rookie Demo.
 */

// Upload
export interface UploadResponse {
  job_id: string
  message: string
  files_received: number
}

// Process
export interface ProcessResponse {
  job_id: string
  status: string
  message: string
}

// Job Status
export interface JobStatusResponse {
  job_id: string
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed' | 'escalated'
  progress: number
  current_stage: string
  message: string | null
}

// Progress Event (from SSE)
export interface ProgressEvent {
  stage:
    | 'uploading'
    | 'scanning'
    | 'classifying'
    | 'extracting'
    | 'review'
    | 'calculating'
    | 'generating'
    | 'complete'
  progress: number
  message: string
  document?: string
  document_type?: string
  confidence?: number
  status?: 'completed' | 'failed' | 'escalated'
}

// Income breakdown
export interface IncomeBreakdown {
  total_wages: string
  total_interest: string
  total_dividends: string
  total_qualified_dividends: string
  total_nec: string
  total_retirement_distributions: string
  total_unemployment: string
  total_state_tax_refund: string
  total_income: string
  federal_withholding: string
}

// Tax calculation
export interface TaxCalculation {
  taxable_income: string
  gross_tax: string
  credits_applied: string
  final_liability: string
  refundable_credits: string
  effective_rate: string
}

// Variance item
export interface VarianceItem {
  field: string
  current_value: string
  prior_value: string
  variance_pct: string
  direction: 'increase' | 'decrease'
}

// Extraction item
export interface ExtractionItem {
  filename: string
  document_type: string
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  classification_confidence?: number | null
  classification_reasoning?: string | null
  classification_overridden?: boolean
  classification_override_source?: string | null
  classification_original_type?: string | null
  classification_original_confidence?: number | null
  classification_original_reasoning?: string | null
  key_fields: Record<string, string>
}

export interface ExtractionPreviewResponse {
  job_id: string
  status: string
  message: string
  extractions: ExtractionItem[]
  escalations: string[]
}

export interface UploadedDocumentItem {
  artifact_id: number
  filename: string
  content_type: string
  size: number | null
  uploaded_at: string
}

export interface UploadedDocumentsResponse {
  job_id: string
  files: UploadedDocumentItem[]
}

// Full results
export interface ResultsResponse {
  job_id: string
  status: string
  client_name: string
  tax_year: number
  filing_status: string
  overall_confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  income: IncomeBreakdown
  tax: TaxCalculation
  extractions: ExtractionItem[]
  variances: VarianceItem[]
  escalations: string[]
  drake_worksheet_available: boolean
  preparer_notes_available: boolean
}

// Filing status options
export type FilingStatus = 'single' | 'mfj' | 'mfs' | 'hoh'

export type DocumentModelOption =
  | 'claude-opus-4-6'
  | 'claude-sonnet-4-5-20250929'

export const MODEL_LABELS: Record<DocumentModelOption, string> = {
  'claude-opus-4-6': 'Claude Opus 4.6',
  'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
}

export const FILING_STATUS_LABELS: Record<FilingStatus, string> = {
  single: 'Single',
  mfj: 'Married Filing Jointly',
  mfs: 'Married Filing Separately',
  hoh: 'Head of Household',
}

// Document type options for user selection
export type DocumentTypeOption =
  | 'auto'
  | 'W2'
  | '1099-INT'
  | '1099-DIV'
  | '1099-NEC'
  | '1098'
  | '1099-R'
  | '1099-G'
  | '1098-T'
  | '5498'
  | '1099-S'

export const DOCUMENT_TYPE_LABELS: Record<DocumentTypeOption, string> = {
  auto: 'Auto-detect',
  W2: 'W-2 (Wages)',
  '1099-INT': '1099-INT (Interest)',
  '1099-DIV': '1099-DIV (Dividends)',
  '1099-NEC': '1099-NEC (Self-Employment)',
  '1098': '1098 (Mortgage Interest)',
  '1099-R': '1099-R (Retirement Distribution)',
  '1099-G': '1099-G (Government Payments)',
  '1098-T': '1098-T (Tuition)',
  '5498': '5498 (IRA Contribution)',
  '1099-S': '1099-S (Real Estate)',
}

// File with selected form type
export interface UploadFile {
  file: File
  formType: DocumentTypeOption
}
