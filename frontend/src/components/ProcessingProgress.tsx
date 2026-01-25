import { useEffect, useState } from 'react'
import { Check, Loader2, Circle, FileSearch, FileText, Calculator, FileOutput, Sparkles } from 'lucide-react'
import { cn } from '../lib/utils'
import { subscribeToProgress } from '../api/demo'
import type { ProgressEvent } from '../types/api'
import * as Progress from '@radix-ui/react-progress'

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
  { key: 'classifying', label: 'Classifying documents', icon: FileText },
  { key: 'extracting', label: 'Extracting data', icon: FileText },
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

  useEffect(() => {
    const cleanup = subscribeToProgress(
      jobId,
      (event: ProgressEvent) => {
        setProgress(event.progress)
        setMessage(event.message)
        
        if (event.stage && event.stage !== 'complete') {
          // Update stage statuses
          setStageStatuses(prev => {
            const updated = { ...prev }
            const stageIndex = STAGES.findIndex(s => s.key === event.stage)
            
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
        }
        
        // Track document progress
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
                      status: event.stage === 'extracting' ? 'complete' as const : d.status,
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
        
        // Handle completion
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
      (error) => onError(error.message),
      () => {}
    )
    
    return cleanup
  }, [jobId, onComplete, onError])

  const getStageIcon = (_stage: StageInfo, status: StageStatus) => {
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
          <Loader2 className="w-4 h-4 text-primary-600 animate-spin" />
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
          <h2 className="font-display text-xl font-semibold text-surface-900">
            Processing Documents
          </h2>
          <p className="text-sm text-surface-500">{message}</p>
        </div>
      </div>

      {/* Progress bar */}
      <Progress.Root
        className="relative overflow-hidden bg-surface-100 rounded-full w-full h-3 mb-8"
        value={progress}
      >
        <Progress.Indicator
          className="bg-primary-500 h-full transition-all duration-300 ease-out rounded-full"
          style={{ width: `${progress}%` }}
        />
      </Progress.Root>

      {/* Stages */}
      <div className="space-y-3">
        {STAGES.map((stage, index) => {
          const status = stageStatuses[stage.key]
          
          return (
            <div key={stage.key} className="flex items-center gap-4">
              {/* Connector line */}
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
              
              {/* Label */}
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

      {/* Document details */}
      {documents.length > 0 && (
        <div className="mt-8 pt-6 border-t border-surface-200">
          <h3 className="text-sm font-medium text-surface-700 mb-3">
            Documents Processed
          </h3>
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.name}
                className="flex items-center gap-3 text-sm"
              >
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
                  <span className="text-xs text-surface-500 tabular-nums">
                    {(doc.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
