import { type ReactNode, useState } from 'react'
import { BriefcaseBusiness, FileStack, LayoutDashboard } from 'lucide-react'
import { DemoWorkspace } from './components/DemoWorkspace'
import { OperationsWorkspace } from './components/OperationsWorkspace'

type WorkspaceMode = 'operations' | 'demo'

export default function App() {
  const [mode, setMode] = useState<WorkspaceMode>('operations')

  return (
    <div className="min-h-dvh bg-[radial-gradient(circle_at_20%_0%,rgba(217,119,6,0.12),transparent_36%),radial-gradient(circle_at_100%_20%,rgba(120,113,108,0.1),transparent_40%),linear-gradient(180deg,#fafaf9_0%,#f5f5f4_100%)]">
      <a
        href="#app-main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:text-surface-900 focus:px-3 focus:py-2 focus:rounded-lg focus:shadow"
      >
        Skip to main content
      </a>
      <header className="border-b border-surface-200/80 bg-white/85 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center shadow-sm">
                <BriefcaseBusiness className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="font-display text-xl font-semibold text-surface-900">Rookie Workspace</h1>
                <p className="text-sm text-surface-500">
                  Operations queue and personal tax processing
                </p>
              </div>
            </div>

            <div
              className="inline-flex rounded-xl border border-surface-200 p-1 bg-white w-full md:w-auto"
              role="tablist"
              aria-label="Workspace mode"
            >
              <WorkspaceToggle
                active={mode === 'operations'}
                icon={<LayoutDashboard className="w-4 h-4" />}
                label="Operations"
                onClick={() => setMode('operations')}
              />
              <WorkspaceToggle
                active={mode === 'demo'}
                icon={<FileStack className="w-4 h-4" />}
                label="Demo"
                onClick={() => setMode('demo')}
              />
            </div>
          </div>
        </div>
      </header>

      <main
        id="app-main"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8"
        tabIndex={-1}
      >
        {mode === 'operations' ? <OperationsWorkspace /> : <DemoWorkspace />}
      </main>

      <footer className="border-t border-surface-200/80 bg-white/70 backdrop-blur-sm mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-sm text-surface-500 text-center">
            Rookie • Humans approve, AI prepares
          </p>
        </div>
      </footer>
    </div>
  )
}

function WorkspaceToggle({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 flex-1 md:flex-none ${
        active
          ? 'bg-primary-600 text-white shadow-sm'
          : 'text-surface-700 hover:bg-surface-100'
      }`}
      aria-pressed={active}
      role="tab"
      aria-selected={active}
    >
      {icon}
      {label}
    </button>
  )
}
