import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { UploadZone } from './components/UploadZone'
import { ProcessingProgress } from './components/ProcessingProgress'
import { ResultsPanel } from './components/ResultsPanel'
import { uploadDocuments, startProcessing, getResults } from './api/demo'
import type { FilingStatus, ResultsResponse } from './types/api'

type AppState = 'upload' | 'processing' | 'results' | 'error'

export default function App() {
  const [state, setState] = useState<AppState>('upload')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  // Fetch results when processing completes
  const { data: results } = useQuery<ResultsResponse>({
    queryKey: ['results', jobId],
    queryFn: () => getResults(jobId!),
    enabled: state === 'results' && !!jobId,
    staleTime: Infinity,
  })

  const handleSubmit = useCallback(
    async (files: File[], clientName: string, taxYear: number, filingStatus: FilingStatus) => {
      try {
        setIsUploading(true)
        setError(null)
        
        // Upload files
        const uploadResult = await uploadDocuments(files, clientName, taxYear, filingStatus)
        setJobId(uploadResult.job_id)
        
        // Start processing
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
    <div className="min-h-dvh bg-surface-50">
      {/* Header */}
      <header className="border-b border-surface-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14,2 14,8 20,8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <line x1="10" y1="9" x2="8" y2="9" />
              </svg>
            </div>
            <div>
              <h1 className="font-display text-xl font-semibold text-surface-900">
                Rookie
              </h1>
              <p className="text-sm text-surface-500">
                Personal Tax Demo
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload state */}
        {state === 'upload' && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="font-display text-3xl font-semibold text-surface-900 text-balance">
                Process Tax Documents
              </h2>
              <p className="text-surface-500 mt-2 text-pretty max-w-lg mx-auto">
                Upload W-2s and 1099s. Rookie will extract the data, calculate taxes, 
                and generate worksheets for your review.
              </p>
            </div>
            <UploadZone onSubmit={handleSubmit} isLoading={isUploading} />
          </div>
        )}

        {/* Processing state */}
        {state === 'processing' && jobId && (
          <div className="max-w-lg mx-auto">
            <ProcessingProgress
              jobId={jobId}
              onComplete={handleProcessingComplete}
              onError={handleProcessingError}
            />
          </div>
        )}

        {/* Results state */}
        {state === 'results' && results && (
          <ResultsPanel results={results} onReset={handleReset} />
        )}

        {/* Error state */}
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
              <p className="text-surface-500 mb-6">
                {error || 'An unexpected error occurred'}
              </p>
              <button
                type="button"
                onClick={handleReset}
                className="btn-primary"
              >
                Try Again
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-200 bg-white mt-auto">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-sm text-surface-400 text-center">
            Rookie • Your AI junior accountant • Demo Mode
          </p>
        </div>
      </footer>
    </div>
  )
}
