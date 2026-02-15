import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Calculator,
  Check,
  Circle,
  ClipboardCheck,
  Eye,
  FileOutput,
  FileSearch,
  FileText,
  Loader2,
  Sparkles,
} from 'lucide-react'
import * as Progress from '@radix-ui/react-progress'
import { cn } from '../lib/utils'
import {
  getExtractionPreview,
  getUploadedDocuments,
  getUploadedDocumentViewUrl,
  subscribeToProgress,
  verifyExtractionPreview,
} from '../api/demo'
import type {
  ExtractionPreviewResponse,
  ProgressEvent,
  UploadedDocumentItem,
} from '../types/api'

interface ProcessingProgressProps {
  jobId: string
  onComplete: () => void
  onError: (error: string) => void
}

interface StageInfo {
  key: string
  label: string
  icon: typeof FileSearch
}

const STAGES: StageInfo[] = [
  { key: 'scanning', label: 'Scanning documents', icon: FileSearch },
  { key: 'extracting', label: 'Extracting fields', icon: FileText },
  { key: 'review', label: 'Verify extracted data', icon: ClipboardCheck },
  { key: 'calculating', label: 'Calculating tax', icon: Calculator },
  { key: 'generating', label: 'Generating outputs', icon: FileOutput },
]

type StageStatus = 'pending' | 'active' | 'complete'

interface DocumentProgress {
  name: string
  type?: string
  confidence?: number
  status: 'processing' | 'complete'
}

function confidenceTone(confidence: string): string {
  if (confidence === 'HIGH') return 'bg-emerald-100 text-emerald-700 border-emerald-200'
  if (confidence === 'MEDIUM') return 'bg-amber-100 text-amber-700 border-amber-200'
  return 'bg-rose-100 text-rose-700 border-rose-200'
}

function formatFileSize(size: number | null): string {
  if (!size || size <= 0) return 'Unknown size'
  const kb = size / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

export function ProcessingProgress({ jobId, onComplete, onError }: ProcessingProgressProps) {
  const [progress, setProgress] = useState(0)
  const [stageStatuses, setStageStatuses] = useState<Record<string, StageStatus>>(() => {
    const initial: Record<string, StageStatus> = {}
    STAGES.forEach((s, i) => {
      initial[s.key] = i === 0 ? 'active' : 'pending'
    })
    return initial
  })
  const [documents, setDocuments] = useState<DocumentProgress[]>([])
  const [message, setMessage] = useState('Starting...')

  const [preview, setPreview] = useState<ExtractionPreviewResponse | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [verifyingPreview, setVerifyingPreview] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [showPreviewPanel, setShowPreviewPanel] = useState(false)
  const previewRequestedRef = useRef(false)
  const [showFileViewer, setShowFileViewer] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedDocumentItem[]>([])
  const [selectedUploadedFile, setSelectedUploadedFile] = useState<UploadedDocumentItem | null>(null)
  const [loadingUploadedFiles, setLoadingUploadedFiles] = useState(false)
  const [uploadedFilesError, setUploadedFilesError] = useState<string | null>(null)
  const uploadedFilesRequestedRef = useRef(false)

  useEffect(() => {
    const cleanup = subscribeToProgress(
      jobId,
      (event: ProgressEvent) => {
        setProgress(event.progress)
        setMessage(event.message)

        if (event.stage && event.stage !== 'complete') {
          setStageStatuses(prev => {
            const updated = { ...prev }
            const stageIndex = STAGES.findIndex(s => s.key === event.stage)
            if (stageIndex < 0) {
              return updated
            }

            STAGES.forEach((s, i) => {
              if (i < stageIndex) {
                updated[s.key] = 'complete'
              } else if (i === stageIndex) {
                updated[s.key] = 'active'
              } else {
                updated[s.key] = 'pending'
              }
            })

            return updated
          })

          if (event.stage === 'review') {
            setShowPreviewPanel(true)
            if (!previewRequestedRef.current) {
              previewRequestedRef.current = true
              setLoadingPreview(true)
              setPreviewError(null)
              void getExtractionPreview(jobId)
                .then(data => {
                  setPreview(data)
                })
                .catch(error => {
                  const message = error instanceof Error ? error.message : 'Failed to load extraction preview'
                  setPreviewError(message)
                })
                .finally(() => {
                  setLoadingPreview(false)
                })
            }
          } else if (event.stage === 'calculating' || event.stage === 'generating') {
            setShowPreviewPanel(false)
            setShowFileViewer(false)
            setVerifyingPreview(false)
          }
        }

        if (event.document) {
          const docName = event.document
          setDocuments(prev => {
            const existing = prev.find(d => d.name === docName)
            if (existing) {
              return prev.map(d =>
                d.name === docName
                  ? {
                      ...d,
                      type: event.document_type || d.type,
                      confidence: event.confidence || d.confidence,
                      status: event.stage === 'extracting' ? ('complete' as const) : d.status,
                    }
                  : d
              )
            }
            return [
              ...prev,
              {
                name: docName,
                type: event.document_type,
                confidence: event.confidence,
                status: 'processing' as const,
              },
            ]
          })
        }

        if (event.stage === 'complete') {
          setStageStatuses(prev => {
            const updated = { ...prev }
            STAGES.forEach(s => {
              updated[s.key] = 'complete'
            })
            return updated
          })

          if (event.status === 'failed' || event.status === 'escalated') {
            onError(event.message)
          } else {
            onComplete()
          }
        }
      },
      error => onError(error.message),
      () => {}
    )

    return cleanup
  }, [jobId, onComplete, onError])

  const handleVerifyAndContinue = async () => {
    try {
      setVerifyingPreview(true)
      setPreviewError(null)
      await verifyExtractionPreview(jobId)
      setMessage('Verification confirmed. Continuing tax calculation...')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to continue processing'
      setPreviewError(errorMessage)
      setVerifyingPreview(false)
    }
  }

  const loadUploadedFiles = async () => {
    try {
      setLoadingUploadedFiles(true)
      setUploadedFilesError(null)
      const response = await getUploadedDocuments(jobId)
      setUploadedFiles(response.files)
      if (response.files.length > 0) {
        setSelectedUploadedFile(response.files[0])
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load uploaded files'
      setUploadedFilesError(errorMessage)
    } finally {
      setLoadingUploadedFiles(false)
    }
  }

  const handleToggleFileViewer = () => {
    setShowFileViewer(prev => {
      const next = !prev
      if (next && !uploadedFilesRequestedRef.current) {
        uploadedFilesRequestedRef.current = true
        void loadUploadedFiles()
      }
      return next
    })
  }

  const selectedFilePreviewUrl = selectedUploadedFile
    ? getUploadedDocumentViewUrl(jobId, selectedUploadedFile.artifact_id)
    : null

  const getStageIcon = (stage: StageInfo, status: StageStatus) => {
    const StageIcon = stage.icon

    if (status === 'complete') {
      return (
        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
          <Check className="w-4 h-4 text-green-600" />
        </div>
      )
    }

    if (status === 'active') {
      return (
        <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
          {stage.key === 'review' ? (
            <StageIcon className="w-4 h-4 text-primary-600" />
          ) : (
            <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />
          )}
        </div>
      )
    }

    return (
      <div className="w-8 h-8 rounded-full bg-surface-100 flex items-center justify-center">
        <Circle className="w-4 h-4 text-surface-400" />
      </div>
    )
  }

  return (
    <div className="card p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <h2 className="font-display text-xl font-semibold text-surface-900">Processing Documents</h2>
          <p className="text-sm text-surface-500">{message}</p>
        </div>
      </div>

      <Progress.Root
        className="relative overflow-hidden bg-surface-100 rounded-full w-full h-3 mb-8"
        value={progress}
      >
        <Progress.Indicator
          className="bg-primary-500 h-full transition-all duration-300 ease-out rounded-full"
          style={{ width: `${progress}%` }}
        />
      </Progress.Root>

      <div className="space-y-3">
        {STAGES.map((stage, index) => {
          const status = stageStatuses[stage.key]

          return (
            <div key={stage.key} className="flex items-center gap-4">
              <div className="relative">
                {getStageIcon(stage, status)}
                {index < STAGES.length - 1 && (
                  <div
                    className={cn(
                      'absolute left-1/2 top-8 w-0.5 h-6 -translate-x-1/2',
                      status === 'complete' ? 'bg-green-200' : 'bg-surface-200'
                    )}
                  />
                )}
              </div>

              <span
                className={cn(
                  'text-sm font-medium',
                  status === 'complete' && 'text-green-700',
                  status === 'active' && 'text-primary-700',
                  status === 'pending' && 'text-surface-400'
                )}
              >
                {stage.label}
              </span>
            </div>
          )
        })}
      </div>

      {showPreviewPanel && (
        <div className="mt-8 border border-surface-200 rounded-xl bg-gradient-to-br from-white to-surface-50 p-5">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary-100 text-primary-700 flex items-center justify-center shrink-0">
              <ClipboardCheck className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-base font-semibold text-surface-900">Verify Extracted Data</h3>
              <p className="text-sm text-surface-600 mt-1">
                Review the extracted fields below before we run tax calculation.
              </p>
            </div>
          </div>

          {loadingPreview && (
            <div className="mt-4 flex items-center gap-2 text-sm text-surface-600">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading extracted data...
            </div>
          )}

          {previewError && (
            <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {previewError}
            </div>
          )}

          {preview && (
            <>
              {preview.escalations.length > 0 && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                  <div className="flex items-start gap-2 text-sm text-amber-800">
                    <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-medium">Potential issues detected</p>
                      <ul className="mt-1 space-y-1 list-disc list-inside text-amber-700">
                        {preview.escalations.map(item => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-4 max-h-80 overflow-y-auto space-y-3 pr-1">
                {preview.extractions.map(item => (
                  <article key={`${item.filename}-${item.document_type}`} className="rounded-lg border border-surface-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-surface-900 truncate">{item.filename}</p>
                        <p className="text-xs text-surface-500 mt-1">{item.document_type}</p>
                      </div>
                      <span
                        className={cn(
                          'text-xs font-medium px-2.5 py-1 rounded-full border',
                          confidenceTone(item.confidence)
                        )}
                      >
                        {item.confidence}
                      </span>
                    </div>

                    {Object.keys(item.key_fields).length > 0 && (
                      <dl className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {Object.entries(item.key_fields).map(([key, value]) => (
                          <div key={`${item.filename}-${key}`} className="rounded-md bg-surface-50 px-2.5 py-2">
                            <dt className="text-[11px] uppercase tracking-wide text-surface-500">
                              {key.replace(/_/g, ' ')}
                            </dt>
                            <dd className="text-sm font-medium text-surface-800 mt-0.5">{value}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </article>
                ))}
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="btn-secondary px-4 py-2 min-h-9 text-sm"
                    onClick={handleToggleFileViewer}
                  >
                    <Eye className="w-4 h-4" />
                    {showFileViewer ? 'Hide imported files' : 'View imported files'}
                  </button>
                  {uploadedFiles.length > 0 && (
                    <span className="text-xs font-medium text-surface-500">
                      {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void handleVerifyAndContinue()}
                  disabled={verifyingPreview}
                >
                  {verifyingPreview ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  Looks good, continue
                </button>
              </div>

              {showFileViewer && (
                <div className="mt-4 rounded-xl border border-surface-200 bg-white p-3">
                  {loadingUploadedFiles && (
                    <div className="flex items-center gap-2 text-sm text-surface-600 p-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Loading imported files...
                    </div>
                  )}

                  {uploadedFilesError && (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {uploadedFilesError}
                    </div>
                  )}

                  {!loadingUploadedFiles && !uploadedFilesError && uploadedFiles.length === 0 && (
                    <p className="text-sm text-surface-500 p-2">No imported files were found for this job.</p>
                  )}

                  {!loadingUploadedFiles && !uploadedFilesError && uploadedFiles.length > 0 && (
                    <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-3">
                      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                        {uploadedFiles.map(file => (
                          <button
                            key={file.artifact_id}
                            type="button"
                            onClick={() => setSelectedUploadedFile(file)}
                            className={cn(
                              'w-full text-left rounded-lg border px-3 py-2 transition-colors',
                              selectedUploadedFile?.artifact_id === file.artifact_id
                                ? 'border-primary-300 bg-primary-50'
                                : 'border-surface-200 bg-surface-50 hover:bg-surface-100'
                            )}
                          >
                            <p className="text-sm font-medium text-surface-900 truncate">{file.filename}</p>
                            <p className="text-[11px] text-surface-500 mt-1">{formatFileSize(file.size)}</p>
                          </button>
                        ))}
                      </div>

                      <div className="rounded-lg border border-surface-200 bg-surface-50 min-h-[380px] overflow-hidden">
                        {selectedUploadedFile && selectedFilePreviewUrl ? (
                          selectedUploadedFile.content_type.startsWith('image/') ? (
                            <img
                              src={selectedFilePreviewUrl}
                              alt={selectedUploadedFile.filename}
                              className="w-full h-[380px] object-contain bg-white"
                            />
                          ) : (
                            <iframe
                              key={selectedUploadedFile.artifact_id}
                              src={selectedFilePreviewUrl}
                              title={selectedUploadedFile.filename}
                              className="w-full h-[380px] bg-white"
                            />
                          )
                        ) : (
                          <div className="h-[380px] flex items-center justify-center text-surface-500 text-sm">
                            Select a file to preview
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {selectedUploadedFile && (
                    <div className="mt-2 flex items-center justify-between text-xs text-surface-500">
                      <div className="flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5" />
                        <span className="truncate">{selectedUploadedFile.filename}</span>
                      </div>
                      <a
                        href={getUploadedDocumentViewUrl(jobId, selectedUploadedFile.artifact_id, true)}
                        className="text-primary-700 hover:text-primary-800 font-medium"
                      >
                        Download file
                      </a>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {documents.length > 0 && (
        <div className="mt-8 pt-6 border-t border-surface-200">
          <h3 className="text-sm font-medium text-surface-700 mb-3">Documents Processed</h3>
          <div className="space-y-2">
            {documents.map(doc => (
              <div key={doc.name} className="flex items-center gap-3 text-sm">
                {doc.status === 'complete' ? (
                  <Check className="w-4 h-4 text-green-500" />
                ) : (
                  <Loader2 className="w-4 h-4 text-primary-500 animate-spin" />
                )}
                <span className="text-surface-700 truncate flex-1">{doc.name}</span>
                {doc.type && (
                  <span className="px-2 py-0.5 text-xs font-medium bg-surface-100 rounded text-surface-600">
                    {doc.type}
                  </span>
                )}
                {doc.confidence && (
                  <span className="text-xs text-surface-500 tabular-nums">{(doc.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
