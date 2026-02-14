import { useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { UploadZone } from './UploadZone'
import { ProcessingProgress } from './ProcessingProgress'
import { ResultsPanel } from './ResultsPanel'
import { uploadDocuments, startProcessing, getResults } from '../api/demo'
import type {
  FilingStatus,
  ResultsResponse,
  DocumentTypeOption,
  DocumentModelOption,
} from '../types/api'

type AppState = 'upload' | 'processing' | 'results' | 'error'

export function DemoWorkspace() {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AppState>('upload')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const { data: results } = useQuery<ResultsResponse>({
    queryKey: ['results', jobId],
    queryFn: () => getResults(jobId!),
    enabled: state === 'results' && !!jobId,
    staleTime: Infinity,
  })

  const handleSubmit = useCallback(
    async (
      files: File[],
      clientName: string,
      taxYear: number,
      filingStatus: FilingStatus,
      formTypes: DocumentTypeOption[],
      documentModel: DocumentModelOption
    ) => {
      try {
        setIsUploading(true)
        setError(null)

        const uploadResult = await uploadDocuments(
          files,
          clientName,
          taxYear,
          filingStatus,
          formTypes,
          documentModel
        )
        setJobId(uploadResult.job_id)

        await startProcessing(uploadResult.job_id)

        setState('processing')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed')
        setState('error')
      } finally {
        setIsUploading(false)
      }
    },
    []
  )

  const handleProcessingComplete = useCallback(() => {
    setState('results')
  }, [])

  const handleProcessingError = useCallback((errorMessage: string) => {
    setError(errorMessage)
    setState('error')
  }, [])

  const handleReset = useCallback(() => {
    setJobId(null)
    setError(null)
    setState('upload')
  }, [])

  return (
    <>
      {state === 'upload' && (
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="font-display text-3xl font-semibold text-surface-900 text-balance">
              Tax Return
            </h2>
            <p className="text-surface-500 mt-2 text-pretty max-w-lg mx-auto">
              Upload W-2s and 1099s. Rookie will extract the data, ask you to verify it,
              then calculate taxes and generate worksheets for final review.
            </p>
          </div>
          <UploadZone onSubmit={handleSubmit} isLoading={isUploading} />
        </div>
      )}

      {state === 'processing' && jobId && (
        <div className="max-w-lg mx-auto">
          <ProcessingProgress
            jobId={jobId}
            onComplete={handleProcessingComplete}
            onError={handleProcessingError}
          />
        </div>
      )}

      {state === 'results' && results && (
        <ResultsPanel
          results={results}
          onReset={handleReset}
          onReprocess={(currentJobId) => {
            queryClient.invalidateQueries({ queryKey: ['results', currentJobId] })
            setJobId(currentJobId)
            setState('processing')
          }}
        />
      )}

      {state === 'error' && (
        <div className="max-w-lg mx-auto">
          <div className="card p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-8 h-8 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h3 className="font-display text-xl font-semibold text-surface-900 mb-2">
              Something went wrong
            </h3>
            <p className="text-surface-500 mb-6">{error || 'An unexpected error occurred'}</p>
            <button type="button" onClick={handleReset} className="btn-primary">
              Try Again
            </button>
          </div>
        </div>
      )}
    </>
  )
}
