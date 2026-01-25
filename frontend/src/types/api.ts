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
  stage: 'uploading' | 'scanning' | 'classifying' | 'extracting' | 'calculating' | 'generating' | 'complete'
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
  classification_original_type?: string | null
  classification_original_confidence?: number | null
  classification_original_reasoning?: string | null
  key_fields: Record<string, string>
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

export const FILING_STATUS_LABELS: Record<FilingStatus, string> = {
  single: 'Single',
  mfj: 'Married Filing Jointly',
  mfs: 'Married Filing Separately',
  hoh: 'Head of Household',
}
