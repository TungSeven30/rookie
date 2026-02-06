/**
 * Product workflow API types (non-demo).
 */

export type TaskStatus =
  | 'pending'
  | 'assigned'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'escalated'

export interface Client {
  id: number
  name: string
  email: string | null
  created_at: string
  updated_at: string | null
}

export interface ClientListResponse {
  items: Client[]
  total: number
  limit: number
  offset: number
}

export interface Task {
  id: number
  client_id: number
  task_type: string
  status: TaskStatus
  assigned_agent: string | null
  completed_at: string | null
  created_at: string
  updated_at: string | null
}

export interface TaskListResponse {
  items: Task[]
  total: number
  limit: number
  offset: number
}

export interface CreateClientPayload {
  name: string
  email?: string
}

export interface CreateTaskPayload {
  client_id: number
  task_type: string
  assigned_agent?: string
}

export interface UpdateTaskStatusPayload {
  status: TaskStatus
  assigned_agent?: string
  reason?: string
}

export type ScalarValue = string | number

export interface TaskProgress {
  task_id: number
  status: TaskStatus
  assigned_agent: string | null
  progress: number
  current_stage: string
  message: string | null
  updated_at: string | null
}

export interface AgentStatusItem {
  agent: string
  active_tasks: number
  assigned_tasks: number
  in_progress_tasks: number
}

export interface AttentionFlagItem {
  task_id: number
  reason: string
  escalated_at: string
}

export interface DashboardStatus {
  queue_depth: number
  completed_count: number
  failed_count: number
  escalated_count: number
  agent_activity: AgentStatusItem[]
  attention_flags: AttentionFlagItem[]
}

export interface CreateExplicitFeedbackPayload {
  task_id: number
  reviewer_id?: string
  tags: string[]
  original_content: string
  corrected_content?: string
  note?: string
}

export interface FeedbackEntry {
  id: number
  task_id: number
  reviewer_id: string | null
  feedback_type: 'implicit' | 'explicit'
  tags: string[]
  diff_summary: string | null
  created_at: string
}

export interface RunCheckerPayload {
  task_id: number
  source_values: Record<string, ScalarValue>
  prepared_values: Record<string, ScalarValue>
  prior_year_values?: Record<string, ScalarValue>
  documented_reasons?: Record<string, string>
  injected_error_fields?: string[]
}

export interface CheckerFlag {
  code: string
  field: string
  severity: string
  message: string
  source_value: string | null
  prepared_value: string | null
  prior_year_value: string | null
  variance_pct: number | null
}

export interface CheckerReport {
  task_id: number
  status: string
  flag_count: number
  flags: CheckerFlag[]
  approval_blocked: boolean
  error_detection_rate: number | null
}
