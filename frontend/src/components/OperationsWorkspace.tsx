import { type ReactNode, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Flag,
  Loader2,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  ShieldAlert,
  UserPlus,
} from 'lucide-react'
import {
  createClient,
  createExplicitFeedback,
  createImplicitFeedback,
  createTask,
  getDashboardStatus,
  getTask,
  getTaskProgress,
  listClients,
  listTaskFeedback,
  listTasks,
  runChecker,
  updateTaskStatus,
} from '../api/product'
import { cn } from '../lib/utils'
import type {
  CheckerReport,
  Client,
  ScalarValue,
  TaskStatus,
} from '../types/product'

const TASK_STATUSES: Array<TaskStatus | 'all'> = [
  'all',
  'pending',
  'assigned',
  'in_progress',
  'completed',
  'failed',
  'escalated',
]

function statusLabel(status: TaskStatus | 'all'): string {
  if (status === 'all') return 'All statuses'
  return status.replace(/_/g, ' ').replace(/\b\w/g, (s) => s.toUpperCase())
}

function statusPillClass(status: TaskStatus): string {
  switch (status) {
    case 'pending':
      return 'bg-surface-100 text-surface-700 border-surface-200'
    case 'assigned':
      return 'bg-blue-50 text-blue-700 border-blue-200'
    case 'in_progress':
      return 'bg-amber-50 text-amber-700 border-amber-200'
    case 'completed':
      return 'bg-green-50 text-green-700 border-green-200'
    case 'failed':
      return 'bg-red-50 text-red-700 border-red-200'
    case 'escalated':
      return 'bg-rose-50 text-rose-700 border-rose-200'
    default:
      return 'bg-surface-100 text-surface-700 border-surface-200'
  }
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function availableTransitions(status: TaskStatus): TaskStatus[] {
  switch (status) {
    case 'pending':
      return ['assigned']
    case 'assigned':
      return ['in_progress', 'failed', 'escalated']
    case 'in_progress':
      return ['completed', 'failed', 'escalated']
    case 'failed':
      return ['pending']
    case 'completed':
    case 'escalated':
      return []
    default:
      return []
  }
}

function parseScalarRecord(input: string, fieldName: string): Record<string, ScalarValue> {
  const parsed = parseJsonRecord(input, fieldName)
  const output: Record<string, ScalarValue> = {}

  Object.entries(parsed).forEach(([key, value]) => {
    if (typeof value !== 'string' && typeof value !== 'number') {
      throw new Error(`${fieldName} values must be strings or numbers (invalid key: ${key})`)
    }
    output[key] = value
  })

  return output
}

function parseStringRecord(input: string, fieldName: string): Record<string, string> {
  const parsed = parseJsonRecord(input, fieldName)
  const output: Record<string, string> = {}

  Object.entries(parsed).forEach(([key, value]) => {
    if (typeof value !== 'string') {
      throw new Error(`${fieldName} values must be strings (invalid key: ${key})`)
    }
    output[key] = value
  })

  return output
}

function parseJsonRecord(input: string, fieldName: string): Record<string, unknown> {
  let parsed: unknown = {}

  if (input.trim()) {
    try {
      parsed = JSON.parse(input)
    } catch {
      throw new Error(`${fieldName} must be valid JSON`)
    }
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldName} must be a JSON object`)
  }

  return parsed as Record<string, unknown>
}

function parseTags(input: string): string[] {
  return input
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean)
}

interface TaskCreateForm {
  client_id: string
  task_type: string
  assigned_agent: string
}

export function OperationsWorkspace() {
  const queryClient = useQueryClient()

  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all')
  const [clientFilter, setClientFilter] = useState<string>('all')
  const [taskTypeFilter, setTaskTypeFilter] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)

  const [newClientName, setNewClientName] = useState('')
  const [newClientEmail, setNewClientEmail] = useState('')
  const [clientError, setClientError] = useState<string | null>(null)

  const [taskForm, setTaskForm] = useState<TaskCreateForm>({
    client_id: '',
    task_type: 'personal_tax',
    assigned_agent: 'personal_tax_agent',
  })
  const [taskError, setTaskError] = useState<string | null>(null)

  const [transitionAgent, setTransitionAgent] = useState('personal_tax_agent')
  const [transitionReason, setTransitionReason] = useState('')
  const [transitionError, setTransitionError] = useState<string | null>(null)

  const [feedbackReviewerId, setFeedbackReviewerId] = useState('cpa-reviewer')
  const [feedbackTags, setFeedbackTags] = useState('calculation_fix')
  const [feedbackOriginalContent, setFeedbackOriginalContent] = useState('')
  const [feedbackCorrectedContent, setFeedbackCorrectedContent] = useState('')
  const [feedbackNote, setFeedbackNote] = useState('')
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null)

  const [checkerSourceValues, setCheckerSourceValues] = useState(
    '{\n  "wages": 1000,\n  "interest": 100\n}'
  )
  const [checkerPreparedValues, setCheckerPreparedValues] = useState(
    '{\n  "wages": 1000,\n  "interest": 100\n}'
  )
  const [checkerPriorYearValues, setCheckerPriorYearValues] = useState('{}')
  const [checkerDocumentedReasons, setCheckerDocumentedReasons] = useState('{}')
  const [checkerInjectedErrorFields, setCheckerInjectedErrorFields] = useState('')
  const [checkerError, setCheckerError] = useState<string | null>(null)
  const [checkerReport, setCheckerReport] = useState<CheckerReport | null>(null)

  const clientsQuery = useQuery({
    queryKey: ['product-clients'],
    queryFn: () => listClients({ limit: 100, offset: 0 }),
  })

  const tasksQuery = useQuery({
    queryKey: [
      'product-tasks',
      statusFilter,
      clientFilter,
      taskTypeFilter,
      agentFilter,
    ],
    queryFn: () =>
      listTasks({
        status: statusFilter === 'all' ? undefined : statusFilter,
        client_id: clientFilter === 'all' ? undefined : Number(clientFilter),
        task_type: taskTypeFilter.trim() || undefined,
        assigned_agent: agentFilter.trim() || undefined,
        limit: 100,
        offset: 0,
      }),
  })

  const selectedTaskQuery = useQuery({
    queryKey: ['product-task', selectedTaskId],
    queryFn: () => getTask(selectedTaskId!),
    enabled: selectedTaskId !== null,
  })

  const dashboardQuery = useQuery({
    queryKey: ['product-dashboard'],
    queryFn: getDashboardStatus,
    refetchInterval: 30_000,
  })

  const taskProgressQuery = useQuery({
    queryKey: ['product-task-progress', selectedTaskId],
    queryFn: () => getTaskProgress(selectedTaskId!),
    enabled: selectedTaskId !== null,
    refetchInterval: 20_000,
  })

  const feedbackQuery = useQuery({
    queryKey: ['product-task-feedback', selectedTaskId],
    queryFn: () => listTaskFeedback(selectedTaskId!),
    enabled: selectedTaskId !== null,
  })

  const clientMap = useMemo(() => {
    const map = new Map<number, Client>()
    clientsQuery.data?.items.forEach((client) => map.set(client.id, client))
    return map
  }, [clientsQuery.data])

  const createClientMutation = useMutation({
    mutationFn: createClient,
    onSuccess: async (client) => {
      setNewClientName('')
      setNewClientEmail('')
      setClientError(null)
      await queryClient.invalidateQueries({ queryKey: ['product-clients'] })
      setTaskForm((prev) => ({ ...prev, client_id: String(client.id) }))
    },
    onError: (error) => {
      setClientError(error instanceof Error ? error.message : 'Failed to create client')
    },
  })

  const createTaskMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async (task) => {
      setTaskError(null)
      setSelectedTaskId(task.id)
      await queryClient.invalidateQueries({ queryKey: ['product-tasks'] })
      await queryClient.invalidateQueries({ queryKey: ['product-task', task.id] })
      await queryClient.invalidateQueries({ queryKey: ['product-task-progress', task.id] })
      await queryClient.invalidateQueries({ queryKey: ['product-dashboard'] })
    },
    onError: (error) => {
      setTaskError(error instanceof Error ? error.message : 'Failed to create task')
    },
  })

  const transitionMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: number; status: TaskStatus }) => {
      const payload: {
        status: TaskStatus
        assigned_agent?: string
        reason?: string
      } = { status }

      if (status === 'assigned') {
        payload.assigned_agent = transitionAgent.trim()
      }
      if (status === 'failed' || status === 'escalated') {
        payload.reason = transitionReason.trim() || undefined
      }

      return updateTaskStatus(taskId, payload)
    },
    onSuccess: async () => {
      setTransitionError(null)
      setTransitionReason('')
      await queryClient.invalidateQueries({ queryKey: ['product-tasks'] })
      await queryClient.invalidateQueries({ queryKey: ['product-dashboard'] })
      if (selectedTaskId) {
        await queryClient.invalidateQueries({ queryKey: ['product-task', selectedTaskId] })
        await queryClient.invalidateQueries({
          queryKey: ['product-task-progress', selectedTaskId],
        })
      }
    },
    onError: (error) => {
      setTransitionError(error instanceof Error ? error.message : 'Failed to update status')
    },
  })

  const feedbackMutation = useMutation({
    mutationFn: createExplicitFeedback,
    onSuccess: async () => {
      setFeedbackError(null)
      setFeedbackNote('')
      setFeedbackCorrectedContent('')
      setFeedbackSuccess('Explicit feedback saved.')
      if (selectedTaskId) {
        await queryClient.invalidateQueries({
          queryKey: ['product-task-feedback', selectedTaskId],
        })
      }
    },
    onError: (error) => {
      setFeedbackSuccess(null)
      setFeedbackError(error instanceof Error ? error.message : 'Failed to save feedback')
    },
  })

  const implicitFeedbackMutation = useMutation({
    mutationFn: createImplicitFeedback,
    onSuccess: async () => {
      setFeedbackError(null)
      setFeedbackSuccess('Implicit feedback captured from reviewer edits.')
      if (selectedTaskId) {
        await queryClient.invalidateQueries({
          queryKey: ['product-task-feedback', selectedTaskId],
        })
      }
    },
    onError: (error) => {
      setFeedbackSuccess(null)
      setFeedbackError(error instanceof Error ? error.message : 'Failed to save implicit feedback')
    },
  })

  const checkerMutation = useMutation({
    mutationFn: runChecker,
    onSuccess: async (report) => {
      setCheckerError(null)
      setCheckerReport(report)
      await queryClient.invalidateQueries({ queryKey: ['product-dashboard'] })
      await queryClient.invalidateQueries({ queryKey: ['product-tasks'] })
      if (selectedTaskId) {
        await queryClient.invalidateQueries({ queryKey: ['product-task', selectedTaskId] })
        await queryClient.invalidateQueries({
          queryKey: ['product-task-progress', selectedTaskId],
        })
      }
    },
    onError: (error) => {
      setCheckerError(error instanceof Error ? error.message : 'Failed to run checker')
    },
  })

  const tasks = tasksQuery.data?.items ?? []
  const selectedTask = selectedTaskQuery.data ?? null
  const transitions = selectedTask ? availableTransitions(selectedTask.status) : []
  const progress = taskProgressQuery.data
  const feedbackEntries = feedbackQuery.data ?? []
  const dashboard = dashboardQuery.data

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <div>
            <h2 className="font-display text-lg font-semibold text-surface-900">
              Operations Dashboard
            </h2>
            <p className="text-sm text-surface-500">
              Live queue signals for preparers and reviewers.
            </p>
          </div>
          <button
            type="button"
            className="btn-secondary px-3 py-2"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['product-dashboard'] })
              queryClient.invalidateQueries({ queryKey: ['product-tasks'] })
              if (selectedTaskId) {
                queryClient.invalidateQueries({
                  queryKey: ['product-task-progress', selectedTaskId],
                })
                queryClient.invalidateQueries({
                  queryKey: ['product-task-feedback', selectedTaskId],
                })
              }
            }}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh Signals
          </button>
        </div>

        {dashboardQuery.isLoading ? (
          <div className="py-8 text-center text-surface-500">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading dashboard…
          </div>
        ) : !dashboard ? (
          <div className="py-8 text-center text-red-600">Unable to load dashboard.</div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
              <StatCard
                title="Queue Depth"
                value={dashboard.queue_depth}
                icon={<Activity className="w-4 h-4" />}
                accentClass="text-blue-700 bg-blue-50 border-blue-200"
              />
              <StatCard
                title="Completed"
                value={dashboard.completed_count}
                icon={<CheckCircle2 className="w-4 h-4" />}
                accentClass="text-green-700 bg-green-50 border-green-200"
              />
              <StatCard
                title="Failed"
                value={dashboard.failed_count}
                icon={<AlertTriangle className="w-4 h-4" />}
                accentClass="text-red-700 bg-red-50 border-red-200"
              />
              <StatCard
                title="Escalated"
                value={dashboard.escalated_count}
                icon={<ShieldAlert className="w-4 h-4" />}
                accentClass="text-rose-700 bg-rose-50 border-rose-200"
              />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
              <div className="rounded-xl border border-surface-200 bg-white p-4">
                <h3 className="font-display text-base font-semibold text-surface-900 mb-3">
                  Agent Activity
                </h3>
                {dashboard.agent_activity.length === 0 ? (
                  <p className="text-sm text-surface-500">No active agents right now.</p>
                ) : (
                  <div className="space-y-2">
                    {dashboard.agent_activity.map((item) => (
                      <div
                        key={item.agent}
                        className="rounded-lg border border-surface-200 bg-surface-50 p-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium text-surface-800">{item.agent}</p>
                          <span className="text-xs rounded-full px-2 py-0.5 border border-surface-300 bg-white text-surface-700">
                            Active {item.active_tasks}
                          </span>
                        </div>
                        <p className="text-xs text-surface-500 mt-1">
                          Assigned {item.assigned_tasks} • In Progress {item.in_progress_tasks}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-surface-200 bg-white p-4">
                <h3 className="font-display text-base font-semibold text-surface-900 mb-3">
                  Attention Flags
                </h3>
                {dashboard.attention_flags.length === 0 ? (
                  <p className="text-sm text-surface-500">No unresolved escalations.</p>
                ) : (
                  <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
                    {dashboard.attention_flags.map((flag) => (
                      <button
                        key={`${flag.task_id}-${flag.escalated_at}`}
                        type="button"
                        onClick={() => setSelectedTaskId(flag.task_id)}
                        className="w-full text-left rounded-lg border border-rose-200 bg-rose-50 p-3 hover:bg-rose-100 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium text-rose-800">Task #{flag.task_id}</p>
                          <span className="text-xs text-rose-700">
                            {formatDateTime(flag.escalated_at)}
                          </span>
                        </div>
                        <p className="text-xs text-rose-700 mt-1">{flag.reason}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <UserPlus className="w-4 h-4 text-primary-600" />
            <h3 className="font-display text-lg font-semibold text-surface-900">Create Client</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3">
            <input
              className="input"
              placeholder="Client name"
              value={newClientName}
              onChange={(e) => setNewClientName(e.target.value)}
              aria-label="Client name"
            />
            <input
              className="input"
              placeholder="Email (optional)"
              value={newClientEmail}
              onChange={(e) => setNewClientEmail(e.target.value)}
              aria-label="Client email"
            />
            <button
              className="btn-primary px-4"
              type="button"
              disabled={createClientMutation.isPending || !newClientName.trim()}
              onClick={() => {
                createClientMutation.mutate({
                  name: newClientName.trim(),
                  email: newClientEmail.trim() || undefined,
                })
              }}
            >
              {createClientMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Add
            </button>
          </div>
          {clientError && <p className="text-sm text-red-600 mt-2">{clientError}</p>}
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock3 className="w-4 h-4 text-primary-600" />
            <h3 className="font-display text-lg font-semibold text-surface-900">Create Task</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <select
              className="input"
              value={taskForm.client_id}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, client_id: e.target.value }))}
              aria-label="Task client"
            >
              <option value="">Select client</option>
              {clientsQuery.data?.items.map((client) => (
                <option key={client.id} value={String(client.id)}>
                  {client.name}
                </option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Task type"
              value={taskForm.task_type}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, task_type: e.target.value }))}
              aria-label="Task type"
            />
            <input
              className="input"
              placeholder="Assigned agent (optional)"
              value={taskForm.assigned_agent}
              onChange={(e) =>
                setTaskForm((prev) => ({ ...prev, assigned_agent: e.target.value }))
              }
              aria-label="Assigned agent"
            />
          </div>
          <div className="mt-3">
            <button
              className="btn-primary"
              type="button"
              disabled={
                createTaskMutation.isPending ||
                !taskForm.client_id ||
                !taskForm.task_type.trim()
              }
              onClick={() => {
                createTaskMutation.mutate({
                  client_id: Number(taskForm.client_id),
                  task_type: taskForm.task_type.trim(),
                  assigned_agent: taskForm.assigned_agent.trim() || undefined,
                })
              }}
            >
              {createTaskMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Plus className="w-4 h-4" />
              )}
              Create Task
            </button>
            {taskError && <p className="text-sm text-red-600 mt-2">{taskError}</p>}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-6">
        <div className="card p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h3 className="font-display text-lg font-semibold text-surface-900">Task Queue</h3>
            <button
              type="button"
              className="btn-secondary px-3 py-2"
              onClick={() => {
                queryClient.invalidateQueries({ queryKey: ['product-tasks'] })
                if (selectedTaskId) {
                  queryClient.invalidateQueries({ queryKey: ['product-task', selectedTaskId] })
                }
              }}
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <select
              className="input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as TaskStatus | 'all')}
              aria-label="Filter by status"
            >
              {TASK_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>

            <select
              className="input"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              aria-label="Filter by client"
            >
              <option value="all">All clients</option>
              {clientsQuery.data?.items.map((client) => (
                <option key={client.id} value={String(client.id)}>
                  {client.name}
                </option>
              ))}
            </select>

            <input
              className="input"
              placeholder="Filter task type"
              value={taskTypeFilter}
              onChange={(e) => setTaskTypeFilter(e.target.value)}
              aria-label="Filter by task type"
            />

            <input
              className="input"
              placeholder="Filter agent"
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              aria-label="Filter by agent"
            />
          </div>

          {tasksQuery.isLoading ? (
            <div className="py-10 text-center text-surface-500">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
              Loading tasks…
            </div>
          ) : tasks.length === 0 ? (
            <div className="py-10 text-center text-surface-500">No tasks found.</div>
          ) : (
            <div className="space-y-2 max-h-[740px] overflow-y-auto pr-1">
              {tasks.map((task) => {
                const client = clientMap.get(task.client_id)
                const selected = selectedTaskId === task.id
                return (
                  <button
                    key={task.id}
                    type="button"
                    onClick={() => {
                      setSelectedTaskId(task.id)
                      setCheckerReport(null)
                      setFeedbackSuccess(null)
                    }}
                    className={cn(
                      'w-full text-left rounded-xl border p-3 transition-colors',
                      selected
                        ? 'border-primary-400 bg-primary-50/60'
                        : 'border-surface-200 hover:border-surface-300 hover:bg-surface-50'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-surface-900">Task #{task.id}</p>
                      <span
                        className={cn(
                          'text-xs px-2 py-0.5 rounded-full border',
                          statusPillClass(task.status)
                        )}
                      >
                        {statusLabel(task.status)}
                      </span>
                    </div>
                    <p className="text-sm text-surface-600 mt-1">
                      {client?.name ?? `Client ${task.client_id}`} • {task.task_type}
                    </p>
                    <p className="text-xs text-surface-500 mt-1">
                      Agent: {task.assigned_agent ?? '—'} • Created{' '}
                      {formatDateTime(task.created_at)}
                    </p>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="card p-5">
          <h3 className="font-display text-lg font-semibold text-surface-900 mb-4">Task Detail</h3>

          {!selectedTaskId ? (
            <div className="py-12 text-center text-surface-500">
              Select a task from the queue to manage status and review details.
            </div>
          ) : selectedTaskQuery.isLoading ? (
            <div className="py-12 text-center text-surface-500">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
              Loading task…
            </div>
          ) : !selectedTask ? (
            <div className="py-12 text-center text-red-600">Task not found.</div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <InfoField label="Task ID" value={`#${selectedTask.id}`} />
                <InfoField
                  label="Status"
                  value={statusLabel(selectedTask.status)}
                  valueClass={statusPillClass(selectedTask.status)}
                  pill
                />
                <InfoField
                  label="Client"
                  value={
                    clientMap.get(selectedTask.client_id)?.name ??
                    `Client ${selectedTask.client_id}`
                  }
                />
                <InfoField label="Type" value={selectedTask.task_type} />
                <InfoField label="Assigned Agent" value={selectedTask.assigned_agent ?? '—'} />
                <InfoField label="Completed At" value={formatDateTime(selectedTask.completed_at)} />
              </div>

              <div className="rounded-xl border border-surface-200 p-4 bg-white space-y-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary-600" />
                  <p className="text-sm font-medium text-surface-800">Processing Progress</p>
                </div>
                {taskProgressQuery.isLoading ? (
                  <p className="text-sm text-surface-500">Loading progress…</p>
                ) : !progress ? (
                  <p className="text-sm text-surface-500">No progress snapshot available.</p>
                ) : (
                  <>
                    <div className="w-full h-2 rounded-full bg-surface-200 overflow-hidden">
                      <div
                        className="h-full bg-primary-600 transition-all duration-300"
                        style={{
                          width: `${Math.min(Math.max(progress.progress, 0), 100)}%`,
                        }}
                      />
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-surface-600">
                      <span>{progress.progress}%</span>
                      <span>•</span>
                      <span>{progress.current_stage}</span>
                      <span>•</span>
                      <span>{formatDateTime(progress.updated_at)}</span>
                    </div>
                    {progress.message && (
                      <p className="text-sm text-surface-700">{progress.message}</p>
                    )}
                  </>
                )}
              </div>

              {transitions.length === 0 ? (
                <div className="rounded-xl border border-surface-200 bg-surface-50 p-4 text-sm text-surface-600">
                  This task is in a terminal state and has no further transitions.
                </div>
              ) : (
                <div className="rounded-xl border border-surface-200 p-4 space-y-3">
                  <p className="text-sm font-medium text-surface-800">Available Actions</p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <input
                      className="input"
                      placeholder="Assign agent (required for Assign)"
                      value={transitionAgent}
                      onChange={(e) => setTransitionAgent(e.target.value)}
                      aria-label="Agent for status transition"
                    />
                    <input
                      className="input"
                      placeholder="Reason (for Fail/Escalate)"
                      value={transitionReason}
                      onChange={(e) => setTransitionReason(e.target.value)}
                      aria-label="Reason for status transition"
                    />
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {transitions.map((nextStatus) => (
                      <button
                        key={nextStatus}
                        type="button"
                        className={cn(
                          'btn-secondary px-3 py-2',
                          nextStatus === 'completed' &&
                            'bg-green-600 text-white hover:bg-green-700 border-green-600',
                          nextStatus === 'failed' &&
                            'bg-red-600 text-white hover:bg-red-700 border-red-600',
                          nextStatus === 'escalated' &&
                            'bg-rose-600 text-white hover:bg-rose-700 border-rose-600',
                          nextStatus === 'in_progress' &&
                            'bg-amber-600 text-white hover:bg-amber-700 border-amber-600',
                          nextStatus === 'assigned' &&
                            'bg-blue-600 text-white hover:bg-blue-700 border-blue-600'
                        )}
                        disabled={transitionMutation.isPending}
                        onClick={() => {
                          if (!selectedTask) return
                          if (nextStatus === 'assigned' && !transitionAgent.trim()) {
                            setTransitionError(
                              'Assigned agent is required to move to assigned status.'
                            )
                            return
                          }
                          transitionMutation.mutate({
                            taskId: selectedTask.id,
                            status: nextStatus,
                          })
                        }}
                      >
                        {transitionMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : nextStatus === 'completed' ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : nextStatus === 'failed' ? (
                          <AlertTriangle className="w-4 h-4" />
                        ) : nextStatus === 'escalated' ? (
                          <ShieldAlert className="w-4 h-4" />
                        ) : (
                          <Clock3 className="w-4 h-4" />
                        )}
                        {statusLabel(nextStatus)}
                      </button>
                    ))}
                  </div>
                  {transitionError && <p className="text-sm text-red-600">{transitionError}</p>}
                </div>
              )}

              <div className="rounded-xl border border-surface-200 p-4 bg-white space-y-3">
                <div className="flex items-center gap-2">
                  <Bot className="w-4 h-4 text-primary-600" />
                  <p className="text-sm font-medium text-surface-800">Checker</p>
                </div>
                <p className="text-xs text-surface-500">
                  Provide source/prepared values and optional prior-year context.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <textarea
                    className="input min-h-[120px] font-mono text-xs"
                    value={checkerSourceValues}
                    onChange={(e) => setCheckerSourceValues(e.target.value)}
                    aria-label="Source values JSON"
                  />
                  <textarea
                    className="input min-h-[120px] font-mono text-xs"
                    value={checkerPreparedValues}
                    onChange={(e) => setCheckerPreparedValues(e.target.value)}
                    aria-label="Prepared values JSON"
                  />
                  <textarea
                    className="input min-h-[96px] font-mono text-xs"
                    value={checkerPriorYearValues}
                    onChange={(e) => setCheckerPriorYearValues(e.target.value)}
                    aria-label="Prior year values JSON"
                  />
                  <textarea
                    className="input min-h-[96px] font-mono text-xs"
                    value={checkerDocumentedReasons}
                    onChange={(e) => setCheckerDocumentedReasons(e.target.value)}
                    aria-label="Documented reasons JSON"
                  />
                </div>
                <input
                  className="input"
                  placeholder="Injected error fields (comma-separated, optional)"
                  value={checkerInjectedErrorFields}
                  onChange={(e) => setCheckerInjectedErrorFields(e.target.value)}
                  aria-label="Injected error fields"
                />

                <button
                  type="button"
                  className="btn-secondary px-3 py-2"
                  disabled={checkerMutation.isPending}
                  onClick={() => {
                    if (!selectedTask) return
                    try {
                      const sourceValues = parseScalarRecord(
                        checkerSourceValues,
                        'Source values'
                      )
                      const preparedValues = parseScalarRecord(
                        checkerPreparedValues,
                        'Prepared values'
                      )
                      const priorYearValues = parseScalarRecord(
                        checkerPriorYearValues,
                        'Prior year values'
                      )
                      const documentedReasons = parseStringRecord(
                        checkerDocumentedReasons,
                        'Documented reasons'
                      )
                      const injectedErrorFields = checkerInjectedErrorFields
                        .split(',')
                        .map((value) => value.trim())
                        .filter(Boolean)

                      setCheckerError(null)
                      checkerMutation.mutate({
                        task_id: selectedTask.id,
                        source_values: sourceValues,
                        prepared_values: preparedValues,
                        prior_year_values: priorYearValues,
                        documented_reasons: documentedReasons,
                        injected_error_fields: injectedErrorFields,
                      })
                    } catch (error) {
                      setCheckerError(
                        error instanceof Error ? error.message : 'Invalid checker input'
                      )
                    }
                  }}
                >
                  {checkerMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Bot className="w-4 h-4" />
                  )}
                  Run Checker
                </button>
                {checkerError && <p className="text-sm text-red-600">{checkerError}</p>}

                {checkerReport && (
                  <div className="rounded-lg border border-surface-200 bg-surface-50 p-3 space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-surface-700">
                      <span className="rounded-full border border-surface-300 bg-white px-2 py-0.5">
                        Status {checkerReport.status}
                      </span>
                      <span className="rounded-full border border-surface-300 bg-white px-2 py-0.5">
                        Flags {checkerReport.flag_count}
                      </span>
                      {checkerReport.error_detection_rate !== null && (
                        <span className="rounded-full border border-surface-300 bg-white px-2 py-0.5">
                          Detection {(checkerReport.error_detection_rate * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {checkerReport.flags.length === 0 ? (
                      <p className="text-sm text-surface-600">No flags found.</p>
                    ) : (
                      <div className="space-y-2">
                        {checkerReport.flags.map((flag, index) => (
                          <div
                            key={`${flag.code}-${flag.field}-${index}`}
                            className="rounded-md border border-amber-200 bg-amber-50 p-2"
                          >
                            <p className="text-xs font-medium text-amber-800">
                              {flag.field} • {flag.code} • {flag.severity}
                            </p>
                            <p className="text-xs text-amber-700 mt-1">{flag.message}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-surface-200 p-4 bg-white space-y-3">
                <div className="flex items-center gap-2">
                  <MessageSquarePlus className="w-4 h-4 text-primary-600" />
                  <p className="text-sm font-medium text-surface-800">Reviewer Feedback</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <input
                    className="input"
                    placeholder="Reviewer ID"
                    value={feedbackReviewerId}
                    onChange={(e) => {
                      setFeedbackReviewerId(e.target.value)
                      setFeedbackSuccess(null)
                    }}
                    aria-label="Reviewer ID"
                  />
                  <input
                    className="input"
                    placeholder="Tags (comma-separated)"
                    value={feedbackTags}
                    onChange={(e) => {
                      setFeedbackTags(e.target.value)
                      setFeedbackSuccess(null)
                    }}
                    aria-label="Feedback tags"
                  />
                </div>
                <textarea
                  className="input min-h-[88px]"
                  placeholder="Original content"
                  value={feedbackOriginalContent}
                  onChange={(e) => {
                    setFeedbackOriginalContent(e.target.value)
                    setFeedbackSuccess(null)
                  }}
                  aria-label="Original content"
                />
                <textarea
                  className="input min-h-[88px]"
                  placeholder="Corrected content"
                  value={feedbackCorrectedContent}
                  onChange={(e) => {
                    setFeedbackCorrectedContent(e.target.value)
                    setFeedbackSuccess(null)
                  }}
                  aria-label="Corrected content"
                />
                <input
                  className="input"
                  placeholder="Note (optional)"
                  value={feedbackNote}
                  onChange={(e) => {
                    setFeedbackNote(e.target.value)
                    setFeedbackSuccess(null)
                  }}
                  aria-label="Feedback note"
                />

                <button
                  type="button"
                  className="btn-secondary px-3 py-2"
                  disabled={
                    implicitFeedbackMutation.isPending ||
                    feedbackMutation.isPending ||
                    !feedbackOriginalContent.trim() ||
                    !feedbackCorrectedContent.trim()
                  }
                  onClick={async () => {
                    if (!selectedTask) return
                    const original = feedbackOriginalContent.trim()
                    const corrected = feedbackCorrectedContent.trim()
                    if (original === corrected) {
                      setFeedbackError(
                        'Corrected content must be different to capture implicit feedback.'
                      )
                      return
                    }

                    setFeedbackError(null)
                    try {
                      await implicitFeedbackMutation.mutateAsync({
                        task_id: selectedTask.id,
                        reviewer_id: feedbackReviewerId.trim() || undefined,
                        original_content: original,
                        corrected_content: corrected,
                        tags: parseTags(feedbackTags),
                      })
                    } catch {
                      // onError already sets message
                    }
                  }}
                  aria-label="Save reviewer edit as implicit feedback"
                >
                  {implicitFeedbackMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <MessageSquarePlus className="w-4 h-4" />
                  )}
                  Save Reviewer Edit (Implicit)
                </button>

                <button
                  type="button"
                  className="btn-secondary px-3 py-2"
                  disabled={
                    feedbackMutation.isPending ||
                    implicitFeedbackMutation.isPending ||
                    !feedbackOriginalContent.trim()
                  }
                  onClick={async () => {
                    if (!selectedTask) return
                    const tags = parseTags(feedbackTags)

                    if (tags.length === 0) {
                      setFeedbackError('At least one tag is required.')
                      return
                    }

                    const original = feedbackOriginalContent.trim()
                    const corrected = feedbackCorrectedContent.trim()
                    setFeedbackError(null)
                    try {
                      if (corrected && corrected !== original) {
                        await implicitFeedbackMutation.mutateAsync({
                          task_id: selectedTask.id,
                          reviewer_id: feedbackReviewerId.trim() || undefined,
                          original_content: original,
                          corrected_content: corrected,
                          tags,
                        })
                      }

                      await feedbackMutation.mutateAsync({
                        task_id: selectedTask.id,
                        reviewer_id: feedbackReviewerId.trim() || undefined,
                        tags,
                        original_content: original,
                        corrected_content: corrected || undefined,
                        note: feedbackNote.trim() || undefined,
                      })
                    } catch {
                      // onError already sets message
                    }
                  }}
                  aria-label="Save explicit feedback"
                >
                  {feedbackMutation.isPending || implicitFeedbackMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Flag className="w-4 h-4" />
                  )}
                  Save Explicit Feedback
                </button>
                {feedbackError && <p className="text-sm text-red-600">{feedbackError}</p>}
                {feedbackSuccess && (
                  <p className="text-sm text-green-700" aria-live="polite">
                    {feedbackSuccess}
                  </p>
                )}

                <div className="pt-1">
                  <p className="text-xs uppercase tracking-wide text-surface-500 mb-2">
                    Feedback History
                  </p>
                  {feedbackQuery.isLoading ? (
                    <p className="text-sm text-surface-500">Loading feedback…</p>
                  ) : feedbackEntries.length === 0 ? (
                    <p className="text-sm text-surface-500">No feedback yet.</p>
                  ) : (
                    <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                      {feedbackEntries.map((entry) => (
                        <div
                          key={entry.id}
                          className="rounded-lg border border-surface-200 bg-surface-50 p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span className="text-xs text-surface-700 font-medium">
                              {entry.feedback_type}
                            </span>
                            <span className="text-xs text-surface-500">
                              {formatDateTime(entry.created_at)}
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1 mb-2">
                            {entry.tags.map((tag) => (
                              <span
                                key={`${entry.id}-${tag}`}
                                className="text-xs rounded-full border border-surface-300 bg-white px-2 py-0.5 text-surface-700"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                          {entry.diff_summary && (
                            <p className="text-xs text-surface-600 whitespace-pre-wrap">
                              {entry.diff_summary}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function StatCard({
  title,
  value,
  icon,
  accentClass,
}: {
  title: string
  value: number
  icon: ReactNode
  accentClass: string
}) {
  return (
    <div className="rounded-xl border border-surface-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-surface-600">{title}</p>
        <span className={cn('inline-flex rounded-md border p-1.5', accentClass)}>{icon}</span>
      </div>
      <p className="font-display text-2xl font-semibold text-surface-900 mt-2 tabular-nums">
        {value}
      </p>
    </div>
  )
}

function InfoField({
  label,
  value,
  valueClass,
  pill = false,
}: {
  label: string
  value: string
  valueClass?: string
  pill?: boolean
}) {
  return (
    <div className="rounded-lg border border-surface-200 p-3 bg-white">
      <p className="text-xs uppercase tracking-wide text-surface-500 mb-1">{label}</p>
      {pill ? (
        <span className={cn('inline-flex text-xs px-2 py-0.5 rounded-full border', valueClass)}>
          {value}
        </span>
      ) : (
        <p className={cn('text-sm font-medium text-surface-900 break-words', valueClass)}>
          {value}
        </p>
      )}
    </div>
  )
}
