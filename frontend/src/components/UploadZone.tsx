import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { FileText, X, Upload, User, Calendar, Users, ChevronDown } from 'lucide-react'
import { cn } from '../lib/utils'
import {
  FILING_STATUS_LABELS,
  DOCUMENT_TYPE_LABELS,
  type FilingStatus,
  type DocumentTypeOption,
  type UploadFile,
} from '../types/api'
import * as Select from '@radix-ui/react-select'

interface UploadZoneProps {
  onSubmit: (
    files: File[],
    clientName: string,
    taxYear: number,
    filingStatus: FilingStatus,
    formTypes: DocumentTypeOption[]
  ) => void
  isLoading?: boolean
}

export function UploadZone({ onSubmit, isLoading }: UploadZoneProps) {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([])
  const [clientName, setClientName] = useState('')
  const [taxYear, setTaxYear] = useState(2024)
  const [filingStatus, setFilingStatus] = useState<FilingStatus>('single')

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadFile[] = acceptedFiles.map(file => ({
      file,
      formType: 'auto' as DocumentTypeOption,
    }))
    setUploadFiles(prev => [...prev, ...newFiles])
  }, [])

  const removeFile = (index: number) => {
    setUploadFiles(prev => prev.filter((_, i) => i !== index))
  }

  const updateFormType = (index: number, formType: DocumentTypeOption) => {
    setUploadFiles(prev =>
      prev.map((uf, i) => (i === index ? { ...uf, formType } : uf))
    )
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    disabled: isLoading,
  })

  const handleSubmit = () => {
    if (uploadFiles.length === 0 || !clientName.trim()) return
    const files = uploadFiles.map(uf => uf.file)
    const formTypes = uploadFiles.map(uf => uf.formType)
    onSubmit(files, clientName.trim(), taxYear, filingStatus, formTypes)
  }

  const canSubmit = uploadFiles.length > 0 && clientName.trim().length > 0 && !isLoading

  return (
    <div className="card p-8">
      <h2 className="font-display text-2xl font-semibold text-surface-900 mb-6 text-balance">
        Upload Tax Documents
      </h2>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          'relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors duration-150',
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-surface-300 hover:border-primary-400 hover:bg-surface-50',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          <div className={cn(
            'w-14 h-14 rounded-full flex items-center justify-center transition-colors',
            isDragActive ? 'bg-primary-100' : 'bg-surface-100'
          )}>
            <Upload className={cn(
              'w-6 h-6',
              isDragActive ? 'text-primary-600' : 'text-surface-500'
            )} />
          </div>
          <div>
            <p className="text-surface-900 font-medium">
              {isDragActive ? 'Drop files here' : 'Drag & drop tax documents'}
            </p>
            <p className="text-surface-500 text-sm mt-1">
              or click to browse • PDF, JPG, PNG
            </p>
          </div>
        </div>
      </div>

      {/* File list */}
      {uploadFiles.length > 0 && (
        <div className="mt-6 space-y-2">
          <p className="text-sm font-medium text-surface-700">
            {uploadFiles.length} document{uploadFiles.length !== 1 ? 's' : ''} selected
          </p>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {uploadFiles.map((uploadFile, index) => (
              <div
                key={`${uploadFile.file.name}-${index}`}
                className="flex items-center gap-3 p-3 bg-surface-50 rounded-lg group"
              >
                <FileText className="w-5 h-5 text-surface-500 flex-shrink-0" />
                <span className="text-sm text-surface-700 truncate flex-1 min-w-0">
                  {uploadFile.file.name}
                </span>
                <Select.Root
                  value={uploadFile.formType}
                  onValueChange={(value) => updateFormType(index, value as DocumentTypeOption)}
                  disabled={isLoading}
                >
                  <Select.Trigger className="flex items-center gap-1 px-2 py-1 text-xs bg-white border border-surface-200 rounded hover:border-surface-300 focus:outline-none focus:ring-2 focus:ring-primary-500 min-w-[120px]">
                    <Select.Value />
                    <Select.Icon>
                      <ChevronDown className="w-3 h-3 text-surface-400" />
                    </Select.Icon>
                  </Select.Trigger>
                  <Select.Portal>
                    <Select.Content className="bg-white rounded-lg shadow-lg border border-surface-200 overflow-hidden z-50">
                      <Select.Viewport className="p-1">
                        {(Object.entries(DOCUMENT_TYPE_LABELS) as [DocumentTypeOption, string][]).map(
                          ([value, label]) => (
                            <Select.Item
                              key={value}
                              value={value}
                              className="px-2 py-1.5 text-xs cursor-pointer rounded hover:bg-surface-100 outline-none data-[highlighted]:bg-surface-100"
                            >
                              <Select.ItemText>{label}</Select.ItemText>
                            </Select.Item>
                          )
                        )}
                      </Select.Viewport>
                    </Select.Content>
                  </Select.Portal>
                </Select.Root>
                <span className="text-xs text-surface-400 flex-shrink-0">
                  {(uploadFile.file.size / 1024).toFixed(0)} KB
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(index)
                  }}
                  className="p-1 rounded hover:bg-surface-200 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                  aria-label={`Remove ${uploadFile.file.name}`}
                >
                  <X className="w-4 h-4 text-surface-500" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Form fields */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Client Name */}
        <div>
          <label htmlFor="clientName" className="label flex items-center gap-2">
            <User className="w-4 h-4" />
            Client Name
          </label>
          <input
            id="clientName"
            type="text"
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
            placeholder="John Smith"
            className="input"
            disabled={isLoading}
          />
        </div>

        {/* Tax Year */}
        <div>
          <label htmlFor="taxYear" className="label flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Tax Year
          </label>
          <input
            id="taxYear"
            type="number"
            value={taxYear}
            onChange={(e) => setTaxYear(parseInt(e.target.value))}
            min={2020}
            max={2025}
            className="input tabular-nums"
            disabled={isLoading}
          />
        </div>

        {/* Filing Status */}
        <div>
          <label className="label flex items-center gap-2">
            <Users className="w-4 h-4" />
            Filing Status
          </label>
          <Select.Root
            value={filingStatus}
            onValueChange={(value) => setFilingStatus(value as FilingStatus)}
            disabled={isLoading}
          >
            <Select.Trigger className="input flex items-center justify-between">
              <Select.Value />
              <Select.Icon>
                <svg className="w-4 h-4 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </Select.Icon>
            </Select.Trigger>
            <Select.Portal>
              <Select.Content className="bg-white rounded-lg shadow-lg border border-surface-200 overflow-hidden z-50">
                <Select.Viewport className="p-1">
                  {(Object.entries(FILING_STATUS_LABELS) as [FilingStatus, string][]).map(
                    ([value, label]) => (
                      <Select.Item
                        key={value}
                        value={value}
                        className="px-3 py-2 text-sm cursor-pointer rounded hover:bg-surface-100 outline-none data-[highlighted]:bg-surface-100"
                      >
                        <Select.ItemText>{label}</Select.ItemText>
                      </Select.Item>
                    )
                  )}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-surface-200 bg-surface-50 p-4">
        <div className="text-sm font-medium text-surface-700 mb-2">
          What you will get
        </div>
        <ul className="text-sm text-surface-500 space-y-1">
          <li>• Extraction summary with confidence and source files</li>
          <li>• CPA-ready Drake worksheet and preparer notes</li>
          <li>• Escalation notes when a document needs review</li>
        </ul>
      </div>

      {/* Submit button */}
      <div className="mt-8">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="btn-primary w-full"
        >
          {isLoading ? (
            <>
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Processing...
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              Process Documents
            </>
          )}
        </button>
      </div>
    </div>
  )
}
