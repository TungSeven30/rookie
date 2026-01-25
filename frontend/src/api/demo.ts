/**
 * API client for the Rookie Demo endpoints.
 */

import type {
  UploadResponse,
  ProcessResponse,
  JobStatusResponse,
  ResultsResponse,
  ProgressEvent,
  FilingStatus,
  DocumentTypeOption,
} from '../types/api'

const API_BASE = '/api/demo'
const demoApiKey = import.meta.env.VITE_DEMO_API_KEY

function buildHeaders(): HeadersInit {
  if (!demoApiKey) {
    return {}
  }
  return { 'X-Demo-Api-Key': demoApiKey }
}

/**
 * Upload documents for processing.
 */
export async function uploadDocuments(
  files: File[],
  clientName: string,
  taxYear: number,
  filingStatus: FilingStatus,
  formTypes?: DocumentTypeOption[]
): Promise<UploadResponse> {
  const formData = new FormData()
  
  files.forEach(file => {
    formData.append('files', file)
  })
  formData.append('client_name', clientName)
  formData.append('tax_year', taxYear.toString())
  formData.append('filing_status', filingStatus)
  
  // Send form types as JSON array if provided
  if (formTypes && formTypes.length > 0) {
    formData.append('form_types', JSON.stringify(formTypes))
  }
  
  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: buildHeaders(),
    body: formData,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || 'Upload failed')
  }
  
  return response.json()
}

/**
 * Start processing a job.
 */
export async function startProcessing(jobId: string): Promise<ProcessResponse> {
  const response = await fetch(`${API_BASE}/process/${jobId}`, {
    method: 'POST',
    headers: buildHeaders(),
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start processing' }))
    throw new Error(error.detail || 'Failed to start processing')
  }
  
  return response.json()
}

/**
 * Get job status.
 */
export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await fetch(`${API_BASE}/status/${jobId}`, {
    headers: buildHeaders(),
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get status' }))
    throw new Error(error.detail || 'Failed to get status')
  }
  
  return response.json()
}

/**
 * Get processing results.
 */
export async function getResults(jobId: string): Promise<ResultsResponse> {
  const response = await fetch(`${API_BASE}/results/${jobId}`, {
    headers: buildHeaders(),
  })
  
  if (response.status === 202) {
    throw new Error('Processing still in progress')
  }
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to get results' }))
    throw new Error(error.detail || 'Failed to get results')
  }
  
  return response.json()
}

/**
 * Subscribe to progress events via SSE.
 */
export function subscribeToProgress(
  jobId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): () => void {
  const url = demoApiKey
    ? `${API_BASE}/stream/${jobId}?demo_api_key=${encodeURIComponent(demoApiKey)}`
    : `${API_BASE}/stream/${jobId}`
  const eventSource = new EventSource(url)
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as ProgressEvent
      onEvent(data)
      
      // Check if complete
      if (data.stage === 'complete') {
        eventSource.close()
        onComplete?.()
      }
    } catch (err) {
      console.error('Failed to parse SSE event:', err)
    }
  }
  
  eventSource.onerror = () => {
    eventSource.close()
    onError?.(new Error('Connection lost'))
  }
  
  // Return cleanup function
  return () => {
    eventSource.close()
  }
}

/**
 * Get download URL for output files.
 */
export function getDownloadUrl(jobId: string, fileType: 'worksheet' | 'notes'): string {
  if (demoApiKey) {
    return `${API_BASE}/download/${jobId}/${fileType}?demo_api_key=${encodeURIComponent(demoApiKey)}`
  }
  return `${API_BASE}/download/${jobId}/${fileType}`
}

/**
 * Add additional documents to an existing job.
 */
export async function addDocumentsToJob(
  jobId: string,
  files: File[]
): Promise<UploadResponse> {
  if (files.length === 0) {
    throw new Error('No files selected')
  }

  const formData = new FormData()
  
  files.forEach(file => {
    formData.append('files', file)
  })
  
  const response = await fetch(`${API_BASE}/job/${jobId}/add-documents`, {
    method: 'POST',
    headers: buildHeaders(),
    body: formData,
  })
  
  if (!response.ok) {
    let errorMessage = 'Failed to add documents'
    try {
      const error = await response.json()
      errorMessage = error.detail || error.message || errorMessage
    } catch {
      // If response is not JSON, try to get text
      try {
        const text = await response.text()
        if (text) errorMessage = text
      } catch {
        // Ignore
      }
    }
    throw new Error(errorMessage)
  }
  
  return response.json()
}

/**
 * Delete a job.
 */
export async function deleteJob(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/job/${jobId}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete job' }))
    throw new Error(error.detail || 'Failed to delete job')
  }
}
