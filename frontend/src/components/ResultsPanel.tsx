import { useEffect, useMemo, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useDropzone } from 'react-dropzone'
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FileText,
  RotateCcw,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Upload,
  X,
  Loader2,
} from 'lucide-react'
import { cn } from '../lib/utils'
import { getDownloadUrl, addDocumentsToJob, startProcessing } from '../api/demo'
import type { ResultsResponse } from '../types/api'
import * as Accordion from '@radix-ui/react-accordion'

interface ResultsPanelProps {
  results: ResultsResponse
  onReset: () => void
  onReprocess?: (jobId: string) => void
}

export function ResultsPanel({ results, onReset, onReprocess }: ResultsPanelProps) {
  const { income, tax, extractions, variances, escalations, overall_confidence } = results

  const finalLiability = parseFloat(tax.final_liability.replace(/[$,]/g, ''))
  const withholding = parseFloat(income.federal_withholding.replace(/[$,]/g, ''))
  const refundOrOwed = withholding - finalLiability
  const isRefund = refundOrOwed > 0

  const [notesContent, setNotesContent] = useState<string | null>(null)
  const [notesError, setNotesError] = useState<string | null>(null)
  const [notesLoading, setNotesLoading] = useState(false)
  const [notesExpanded, setNotesExpanded] = useState(false)
  const [expandedDocReasoning, setExpandedDocReasoning] = useState<
    Record<number, boolean>
  >({})
  const [additionalFiles, setAdditionalFiles] = useState<File[]>([])
  const [isAddingDocuments, setIsAddingDocuments] = useState(false)
  const [addDocumentsError, setAddDocumentsError] = useState<string | null>(null)

  const documentTypes = useMemo(
    () => Array.from(new Set(extractions.map((doc) => doc.document_type))),
    [extractions]
  )

  const confidenceCounts = useMemo(() => {
    const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 }
    extractions.forEach((doc) => {
      counts[doc.confidence] += 1
    })
    return counts
  }, [extractions])

  useEffect(() => {
    if (!results.preparer_notes_available) {
      setNotesContent(null)
      setNotesExpanded(false)
      return
    }

    const controller = new AbortController()
    setNotesExpanded(false)
    setExpandedDocReasoning({})
    setNotesLoading(true)
    setNotesError(null)

    fetch(getDownloadUrl(results.job_id, 'notes'), {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error('Unable to load preparer notes')
        }
        return response.text()
      })
      .then((text) => setNotesContent(text))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') {
          setNotesError(error.message)
        }
      })
      .finally(() => setNotesLoading(false))

    return () => controller.abort()
  }, [results.job_id, results.preparer_notes_available])

  const notesLines = notesContent?.split('\n') ?? []
  const hasMoreNotes = notesLines.length > 32
  const previewLines = notesExpanded ? notesLines : notesLines.slice(0, 32)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setAdditionalFiles(prev => [...prev, ...acceptedFiles])
    setAddDocumentsError(null)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    disabled: isAddingDocuments,
  })

  const removeAdditionalFile = (index: number) => {
    setAdditionalFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleAddDocuments = useCallback(async () => {
    if (additionalFiles.length === 0) return

    try {
      setIsAddingDocuments(true)
      setAddDocumentsError(null)

      // Add documents to job
      await addDocumentsToJob(results.job_id, additionalFiles)

      // Start reprocessing
      await startProcessing(results.job_id)

      // Clear files before switching state
      setAdditionalFiles([])

      // Notify parent to switch to processing state
      // This must happen after files are cleared to avoid state issues
      if (onReprocess) {
        // Use setTimeout to ensure state updates complete before switching
        setTimeout(() => {
          onReprocess(results.job_id)
        }, 100)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to add documents'
      setAddDocumentsError(errorMessage)
      console.error('Error adding documents:', err)
    } finally {
      setIsAddingDocuments(false)
    }
  }, [additionalFiles, results.job_id, onReprocess])

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-6">
      <section className="space-y-6">
        {/* Header */}
        <div className="card p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl font-semibold text-surface-900 text-balance">
                {results.client_name}
              </h2>
              <p className="text-surface-500 mt-1">
                Tax Year {results.tax_year} • {results.filing_status.toUpperCase()}
              </p>
              <p className="text-xs text-surface-400 mt-1 font-mono">
                Job ID {results.job_id}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={results.status} />
              <ConfidenceBadge confidence={overall_confidence} />
            </div>
          </div>

          {/* Hero number - refund or owed */}
          <div className="mt-6 p-6 bg-gradient-to-br from-surface-50 to-primary-50/40 rounded-2xl text-center border border-surface-100">
            <p className="text-sm font-medium text-surface-500 mb-2">
              {isRefund ? 'Estimated Refund' : 'Estimated Amount Due'}
            </p>
            <p
              className={cn(
                'font-mono text-4xl md:text-5xl font-semibold tabular-nums',
                isRefund ? 'text-green-600' : 'text-red-600'
              )}
            >
              ${Math.abs(refundOrOwed).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </p>
            <p className="text-sm text-surface-400 mt-2">
              Based on {income.federal_withholding} withheld
            </p>
          </div>
        </div>

        {/* Preparer Notes */}
        <div className="card p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-surface-900">
              <ClipboardList className="w-5 h-5 text-primary-600" />
              <h3 className="font-display text-xl font-semibold">Preparer Notes</h3>
            </div>
            {results.preparer_notes_available && (
              <a
                href={getDownloadUrl(results.job_id, 'notes')}
                download
                className="text-xs font-medium text-primary-700 hover:text-primary-800"
              >
                Download
              </a>
            )}
          </div>
          <div className="mt-4">
            {notesLoading && (
              <p className="text-sm text-surface-500">Loading notes…</p>
            )}
            {notesError && <p className="text-sm text-red-600">{notesError}</p>}
            {!notesLoading && !notesError && notesLines.length === 0 && (
              <p className="text-sm text-surface-500">
                Notes will appear here once the job completes.
              </p>
            )}
            {notesLines.length > 0 && (
              <>
                <div className="notes-markdown text-sm md:text-base text-surface-700 bg-surface-50 border border-surface-200 rounded-xl p-5 max-h-[28rem] overflow-y-auto">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {previewLines.join('\n')}
                  </ReactMarkdown>
                </div>
                {hasMoreNotes && (
                  <button
                    type="button"
                    onClick={() => setNotesExpanded((prev) => !prev)}
                    className="mt-3 text-xs font-medium text-primary-700 hover:text-primary-800"
                  >
                    {notesExpanded ? 'Show less' : 'Show full notes'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Income & Tax Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Income Breakdown */}
          <div className="card p-6">
            <h3 className="font-display text-lg font-semibold text-surface-900 mb-4">
              Income Summary
            </h3>
            <div className="space-y-3">
              <DataRow label="Wages (W-2)" value={income.total_wages} />
              <DataRow label="Interest Income" value={income.total_interest} />
              <DataRow label="Dividends" value={income.total_dividends} />
              <DataRow
                label="Qualified Dividends"
                value={income.total_qualified_dividends}
                secondary
              />
              <DataRow label="Self-Employment (1099-NEC)" value={income.total_nec} />
              <div className="pt-3 border-t border-surface-200">
                <DataRow label="Total Income" value={income.total_income} bold />
              </div>
            </div>
          </div>

          {/* Tax Calculation */}
          <div className="card p-6">
            <h3 className="font-display text-lg font-semibold text-surface-900 mb-4">
              Tax Calculation
            </h3>
            <div className="space-y-3">
              <DataRow label="Taxable Income" value={tax.taxable_income} />
              <DataRow label="Gross Tax" value={tax.gross_tax} />
              <DataRow
                label="Credits Applied"
                value={`(${tax.credits_applied})`}
                className="text-green-600"
              />
              <div className="pt-3 border-t border-surface-200">
                <DataRow label="Net Tax Liability" value={tax.final_liability} bold />
              </div>
              <DataRow label="Effective Rate" value={tax.effective_rate} secondary />
              {parseFloat(tax.refundable_credits.replace(/[$,]/g, '')) > 0 && (
                <DataRow
                  label="Refundable Credits"
                  value={tax.refundable_credits}
                  className="text-green-600"
                />
              )}
            </div>
          </div>
        </div>

        {/* Variances - Prior Year Comparison */}
        {variances.length > 0 && (
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              <h3 className="font-display text-lg font-semibold text-surface-900">
                Prior Year Comparison
              </h3>
            </div>
            <div className="space-y-3">
              {variances.map((v, i) => (
                <div
                  key={i}
                  className="flex items-center gap-4 p-3 bg-amber-50 rounded-lg border border-amber-200"
                >
                  {v.direction === 'increase' ? (
                    <TrendingUp className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-amber-900 capitalize">
                      {v.field.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-amber-700 mt-0.5">
                      {v.prior_value} → {v.current_value}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'text-sm font-mono font-medium tabular-nums',
                      v.direction === 'increase' ? 'text-amber-700' : 'text-amber-600'
                    )}
                  >
                    {v.direction === 'increase' ? '+' : ''}
                    {v.variance_pct}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Escalations */}
        {escalations.length > 0 && (
          <div className="card p-6 border-red-200 bg-red-50">
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <h3 className="font-display text-lg font-semibold text-red-900">
                Requires Review
              </h3>
            </div>
            <ul className="space-y-2">
              {escalations.map((e, i) => (
                <li key={i} className="text-sm text-red-800 flex items-start gap-2">
                  <span className="text-red-400">•</span>
                  {e}
                </li>
              ))}
            </ul>
          </div>
        )}

      </section>

      <aside className="space-y-6">
        {/* Add Additional Documents */}
        <div className="card p-6 border-2 border-primary-200 bg-primary-50/30">
          <div className="flex items-center gap-2 text-surface-900 mb-4">
            <Upload className="w-5 h-5 text-primary-600" />
            <h3 className="font-display text-lg font-semibold">Add Documents</h3>
          </div>
          <p className="text-sm text-surface-500 mb-4">
            Upload additional forms (e.g., deduction documents) to recalculate taxes.
          </p>

          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={cn(
              'relative border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors duration-150',
              isDragActive
                ? 'border-primary-500 bg-primary-50'
                : 'border-surface-300 hover:border-primary-400 hover:bg-surface-50',
              isAddingDocuments && 'opacity-50 cursor-not-allowed'
            )}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-2">
              <Upload className={cn(
                'w-5 h-5',
                isDragActive ? 'text-primary-600' : 'text-surface-500'
              )} />
              <p className="text-sm text-surface-700">
                {isDragActive ? 'Drop files here' : 'Click or drag to add documents'}
              </p>
              <p className="text-xs text-surface-400">
                PDF, JPG, PNG
              </p>
            </div>
          </div>

          {/* File list */}
          {additionalFiles.length > 0 && (
            <div className="mt-4 space-y-2">
              {additionalFiles.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center gap-3 p-2 bg-surface-50 rounded-lg group"
                >
                  <FileText className="w-4 h-4 text-surface-500 flex-shrink-0" />
                  <span className="text-sm text-surface-700 truncate flex-1">
                    {file.name}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeAdditionalFile(index)
                    }}
                    className="p-1 rounded hover:bg-surface-200 opacity-0 group-hover:opacity-100 transition-opacity"
                    disabled={isAddingDocuments}
                    aria-label={`Remove ${file.name}`}
                  >
                    <X className="w-3 h-3 text-surface-500" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Error message */}
          {addDocumentsError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-800">{addDocumentsError}</p>
            </div>
          )}

          {/* Submit button */}
          {additionalFiles.length > 0 && (
            <button
              type="button"
              onClick={handleAddDocuments}
              disabled={isAddingDocuments}
              className="mt-4 btn-primary w-full"
            >
              {isAddingDocuments ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Adding documents...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Add & Recalculate
                </>
              )}
            </button>
          )}
        </div>

        {/* Trust Signals */}
        <div className="card p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-surface-900">
              <ShieldCheck className="w-5 h-5 text-primary-600" />
              <h3 className="font-display text-lg font-semibold">Trust Signals</h3>
            </div>
            <ConfidenceBadge confidence={overall_confidence} size="sm" />
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <MetaRow label="Status" value={formatStatus(results.status)} />
            <MetaRow label="Documents" value={`${extractions.length}`} />
            <MetaRow label="Forms detected" value={documentTypes.join(', ') || '—'} />
            <MetaRow
              label="Confidence"
              value={`${confidenceCounts.HIGH} high • ${confidenceCounts.MEDIUM} med • ${confidenceCounts.LOW} low`}
            />
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <TrustTile label="High" value={confidenceCounts.HIGH} tone="high" />
            <TrustTile label="Medium" value={confidenceCounts.MEDIUM} tone="medium" />
            <TrustTile label="Low" value={confidenceCounts.LOW} tone="low" />
          </div>
        </div>

        {/* Documents Processed */}
        <div className="card p-6">
          <div className="flex items-center justify-between gap-4 mb-4">
            <h3 className="font-display text-lg font-semibold text-surface-900">
              Documents Processed
            </h3>
            <span className="text-xs text-surface-500">
              {extractions.length} total
            </span>
          </div>
          <Accordion.Root type="multiple" className="space-y-2">
            {extractions.map((doc, i) => {
              const reasoningText = doc.classification_overridden
                ? doc.classification_original_reasoning ?? doc.classification_reasoning
                : doc.classification_reasoning
              const summaryItems = summarizeReasoning(reasoningText)
              const hasReasoning = Boolean(reasoningText?.trim())
              const isExpanded = Boolean(expandedDocReasoning[i])

              return (
                <Accordion.Item
                  key={i}
                  value={`doc-${i}`}
                  className="border border-surface-200 rounded-lg overflow-hidden"
                >
                  <Accordion.Trigger className="flex items-center gap-3 w-full p-4 text-left hover:bg-surface-50 transition-colors">
                    <FileText className="w-5 h-5 text-surface-500 flex-shrink-0" />
                    <span className="flex-1 text-sm font-medium text-surface-900 truncate">
                      {doc.filename}
                    </span>
                    <span className="px-2 py-1 text-xs font-medium bg-surface-100 rounded text-surface-600">
                      {doc.document_type}
                    </span>
                    <ConfidenceBadge confidence={doc.confidence} size="sm" />
                    <svg
                      className="w-4 h-4 text-surface-400 transition-transform duration-200 [[data-state=open]>&]:rotate-180"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </Accordion.Trigger>
                  <Accordion.Content className="px-4 pb-4 pt-0">
                    <div className="pl-8 border-l-2 border-surface-200 space-y-3">
                      {Object.entries(doc.key_fields).length > 0 ? (
                        Object.entries(doc.key_fields).map(([key, value]) => (
                          <div key={key} className="flex justify-between text-sm">
                            <span className="text-surface-500 capitalize">
                              {formatKeyLabel(key)}
                            </span>
                            <span className="font-mono text-surface-900 tabular-nums">
                              {formatKeyValue(key, value)}
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-surface-400">
                          No key fields extracted for this document.
                        </p>
                      )}
                      {doc.classification_overridden && (
                        <div className="text-xs text-amber-700">
                          Filename override applied. Classifier predicted{' '}
                          {doc.classification_original_type ?? 'unknown'}
                          {typeof doc.classification_original_confidence === 'number'
                            ? ` (${(doc.classification_original_confidence * 100).toFixed(0)}%)`
                            : ''}
                          .
                        </div>
                      )}
                      {summaryItems.length > 0 && (
                        <div className="text-sm text-surface-600">
                          <p className="text-xs font-medium text-surface-500">
                            {doc.classification_overridden
                              ? 'Original classifier summary'
                              : 'Classifier summary'}
                          </p>
                          <ul className="mt-2 list-disc pl-4 space-y-1">
                            {summaryItems.map((item, idx) => (
                              <li key={`${i}-summary-${idx}`}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {hasReasoning && summaryItems.length > 0 && (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedDocReasoning((prev) => ({
                              ...prev,
                              [i]: !prev[i],
                            }))
                          }
                          className="text-xs font-medium text-primary-700 hover:text-primary-800"
                        >
                          {isExpanded ? 'Hide full reasoning' : 'Show full reasoning'}
                        </button>
                      )}
                      {hasReasoning && (isExpanded || summaryItems.length === 0) && (
                        <div className="text-xs text-surface-500 whitespace-pre-wrap">
                          {reasoningText}
                        </div>
                      )}
                      {typeof doc.classification_confidence === 'number' && (
                        <div className="text-xs text-surface-500">
                          Classifier confidence:{' '}
                          {(doc.classification_confidence * 100).toFixed(0)}%
                        </div>
                      )}
                    </div>
                  </Accordion.Content>
                </Accordion.Item>
              )
            })}
          </Accordion.Root>
        </div>

        {/* Download Outputs */}
        <div className="card p-6">
          <div className="flex items-center gap-2 text-surface-900 mb-4">
            <BadgeCheck className="w-5 h-5 text-primary-600" />
            <h3 className="font-display text-lg font-semibold">Download Outputs</h3>
          </div>
          <div className="flex flex-col gap-3">
            {results.drake_worksheet_available && (
              <a
                href={getDownloadUrl(results.job_id, 'worksheet')}
                download
                className="btn-primary"
              >
                <FileSpreadsheet className="w-5 h-5" />
                Drake Worksheet
                <Download className="w-4 h-4 ml-auto" />
              </a>
            )}
            {results.preparer_notes_available && (
              <a
                href={getDownloadUrl(results.job_id, 'notes')}
                download
                className="btn-secondary"
              >
                <FileText className="w-5 h-5" />
                Preparer Notes
                <Download className="w-4 h-4 ml-auto" />
              </a>
            )}
          </div>
        </div>

        {/* Reset Button */}
        <div className="text-center">
          <button type="button" onClick={onReset} className="btn-secondary w-full">
            <RotateCcw className="w-4 h-4" />
            Process Another Client
          </button>
        </div>
      </aside>
    </div>
  )
}

// Helper components

interface DataRowProps {
  label: string
  value: string
  bold?: boolean
  secondary?: boolean
  className?: string
}

function DataRow({ label, value, bold, secondary, className }: DataRowProps) {
  return (
    <div className="flex justify-between items-center">
      <span className={cn(
        'text-sm',
        secondary ? 'text-surface-400 pl-4' : 'text-surface-600',
        bold && 'font-medium text-surface-900'
      )}>
        {label}
      </span>
      <span className={cn(
        'font-mono tabular-nums',
        secondary ? 'text-sm text-surface-400' : 'text-surface-900',
        bold && 'font-semibold',
        className
      )}>
        {value}
      </span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === 'escalated'
      ? 'bg-amber-100 text-amber-700 border-amber-200'
      : status === 'failed'
        ? 'bg-red-100 text-red-700 border-red-200'
        : 'bg-emerald-100 text-emerald-700 border-emerald-200'

  return (
    <span className={cn('inline-flex items-center gap-1 border rounded-full px-3 py-1 text-xs font-medium', tone)}>
      {formatStatus(status)}
    </span>
  )
}

function formatStatus(status: string) {
  if (status === 'escalated') return 'Needs review'
  if (status === 'failed') return 'Failed'
  return 'Completed'
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-surface-500">{label}</span>
      <span className="font-mono text-surface-900 text-xs">{value}</span>
    </div>
  )
}

function TrustTile({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'high' | 'medium' | 'low'
}) {
  const styles = {
    high: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    medium: 'border-amber-200 bg-amber-50 text-amber-700',
    low: 'border-red-200 bg-red-50 text-red-700',
  }

  return (
    <div className={cn('rounded-xl border px-3 py-2 text-center text-xs font-medium', styles[tone])}>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {label}
    </div>
  )
}

function formatKeyLabel(key: string) {
  if (key === 'flags') return 'Flags'
  return key.replace(/_/g, ' ')
}

function formatKeyValue(key: string, value: string) {
  if (key === 'flags') {
    return value.replace(/_/g, ' ')
  }
  return value
}

function summarizeReasoning(
  reasoning: string | null | undefined,
  maxItems = 3
): string[] {
  if (!reasoning) {
    return []
  }
  const normalized = reasoning.replace(/\s+/g, ' ').trim()
  if (!normalized) {
    return []
  }

  const numbered = normalized
    .split(/\s*(?:\d+\)|\d+\.)\s+/)
    .filter(Boolean)
  if (numbered.length > 1) {
    const [preamble, ...items] = numbered
    const candidate = preamble && preamble.length <= 120 ? [preamble, ...items] : items
    return (candidate.length ? candidate : numbered).slice(0, maxItems)
  }

  const sentences = normalized.match(/[^.!?]+[.!?]?/g) ?? []
  return sentences.map((sentence) => sentence.trim()).filter(Boolean).slice(0, maxItems)
}

interface ConfidenceBadgeProps {
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  size?: 'sm' | 'md'
}

function ConfidenceBadge({ confidence, size = 'md' }: ConfidenceBadgeProps) {
  const colors = {
    HIGH: 'bg-green-100 text-green-700 border-green-200',
    MEDIUM: 'bg-amber-100 text-amber-700 border-amber-200',
    LOW: 'bg-red-100 text-red-700 border-red-200',
  }
  
  const icons = {
    HIGH: <CheckCircle2 className={cn(size === 'sm' ? 'w-3 h-3' : 'w-4 h-4')} />,
    MEDIUM: <AlertTriangle className={cn(size === 'sm' ? 'w-3 h-3' : 'w-4 h-4')} />,
    LOW: <AlertTriangle className={cn(size === 'sm' ? 'w-3 h-3' : 'w-4 h-4')} />,
  }
  
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 border rounded-full font-medium',
      colors[confidence],
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
    )}>
      {icons[confidence]}
      {confidence}
    </span>
  )
}
