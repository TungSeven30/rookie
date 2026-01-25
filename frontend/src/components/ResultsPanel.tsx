import { Download, FileSpreadsheet, FileText, AlertTriangle, CheckCircle2, TrendingUp, TrendingDown, RotateCcw } from 'lucide-react'
import { cn } from '../lib/utils'
import { getDownloadUrl } from '../api/demo'
import type { ResultsResponse } from '../types/api'
import * as Accordion from '@radix-ui/react-accordion'

interface ResultsPanelProps {
  results: ResultsResponse
  onReset: () => void
}

export function ResultsPanel({ results, onReset }: ResultsPanelProps) {
  const { income, tax, extractions, variances, escalations, overall_confidence } = results
  
  // Parse final liability to determine refund vs owed
  const finalLiability = parseFloat(tax.final_liability.replace(/[$,]/g, ''))
  const withholding = parseFloat(income.federal_withholding.replace(/[$,]/g, ''))
  const refundOrOwed = withholding - finalLiability
  const isRefund = refundOrOwed > 0
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-display text-2xl font-semibold text-surface-900 text-balance">
              {results.client_name}
            </h2>
            <p className="text-surface-500 mt-1">
              Tax Year {results.tax_year} • {results.filing_status.toUpperCase()}
            </p>
          </div>
          <ConfidenceBadge confidence={overall_confidence} />
        </div>
        
        {/* Hero number - refund or owed */}
        <div className="mt-6 p-6 bg-surface-50 rounded-xl text-center">
          <p className="text-sm font-medium text-surface-500 mb-2">
            {isRefund ? 'Estimated Refund' : 'Estimated Amount Due'}
          </p>
          <p className={cn(
            'font-mono text-4xl md:text-5xl font-semibold tabular-nums',
            isRefund ? 'text-green-600' : 'text-red-600'
          )}>
            ${Math.abs(refundOrOwed).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
          <p className="text-sm text-surface-400 mt-2">
            Based on {income.federal_withholding} withheld
          </p>
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
            <DataRow label="Qualified Dividends" value={income.total_qualified_dividends} secondary />
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
            <DataRow label="Credits Applied" value={`(${tax.credits_applied})`} className="text-green-600" />
            <div className="pt-3 border-t border-surface-200">
              <DataRow label="Net Tax Liability" value={tax.final_liability} bold />
            </div>
            <DataRow label="Effective Rate" value={tax.effective_rate} secondary />
            {parseFloat(tax.refundable_credits.replace(/[$,]/g, '')) > 0 && (
              <DataRow label="Refundable Credits" value={tax.refundable_credits} className="text-green-600" />
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
                <span className={cn(
                  'text-sm font-mono font-medium tabular-nums',
                  v.direction === 'increase' ? 'text-amber-700' : 'text-amber-600'
                )}>
                  {v.direction === 'increase' ? '+' : ''}{v.variance_pct}
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

      {/* Documents Processed */}
      <div className="card p-6">
        <h3 className="font-display text-lg font-semibold text-surface-900 mb-4">
          Documents Processed
        </h3>
        <Accordion.Root type="multiple" className="space-y-2">
          {extractions.map((doc, i) => (
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </Accordion.Trigger>
              <Accordion.Content className="px-4 pb-4 pt-0">
                <div className="pl-8 border-l-2 border-surface-200 space-y-2">
                  {Object.entries(doc.key_fields).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-sm">
                      <span className="text-surface-500 capitalize">{key}</span>
                      <span className="font-mono text-surface-900 tabular-nums">{value}</span>
                    </div>
                  ))}
                </div>
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </div>

      {/* Download Buttons */}
      <div className="card p-6">
        <h3 className="font-display text-lg font-semibold text-surface-900 mb-4">
          Download Outputs
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          {results.drake_worksheet_available && (
            <a
              href={getDownloadUrl(results.job_id, 'worksheet')}
              download
              className="btn-primary flex-1"
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
              className="btn-secondary flex-1"
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
        <button
          type="button"
          onClick={onReset}
          className="btn-secondary"
        >
          <RotateCcw className="w-4 h-4" />
          Process Another Client
        </button>
      </div>
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
