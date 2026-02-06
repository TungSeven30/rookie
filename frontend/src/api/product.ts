/**
 * API client for product workflow endpoints.
 */

import type {
  CheckerReport,
  Client,
  ClientListResponse,
  CreateExplicitFeedbackPayload,
  CreateClientPayload,
  CreateTaskPayload,
  DashboardStatus,
  FeedbackEntry,
  RunCheckerPayload,
  Task,
  TaskListResponse,
  TaskProgress,
  TaskStatus,
  UpdateTaskStatusPayload,
} from '../types/product'

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      query.set(key, String(value))
    }
  })
  const value = query.toString()
  return value ? `?${value}` : ''
}

async function parseResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({ detail: fallbackMessage }))
    throw new Error(errorPayload.detail || fallbackMessage)
  }
  return response.json() as Promise<T>
}

export async function listClients(options?: {
  search?: string
  limit?: number
  offset?: number
}): Promise<ClientListResponse> {
  const query = buildQuery({
    search: options?.search,
    limit: options?.limit,
    offset: options?.offset,
  })
  const response = await fetch(`/api/clients${query}`)
  return parseResponse<ClientListResponse>(response, 'Failed to list clients')
}

export async function createClient(payload: CreateClientPayload): Promise<Client> {
  const response = await fetch('/api/clients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<Client>(response, 'Failed to create client')
}

export async function listTasks(options?: {
  client_id?: number
  task_type?: string
  assigned_agent?: string
  status?: TaskStatus
  limit?: number
  offset?: number
}): Promise<TaskListResponse> {
  const query = buildQuery({
    client_id: options?.client_id,
    task_type: options?.task_type,
    assigned_agent: options?.assigned_agent,
    status: options?.status,
    limit: options?.limit,
    offset: options?.offset,
  })
  const response = await fetch(`/api/tasks${query}`)
  return parseResponse<TaskListResponse>(response, 'Failed to list tasks')
}

export async function createTask(payload: CreateTaskPayload): Promise<Task> {
  const response = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<Task>(response, 'Failed to create task')
}

export async function getTask(taskId: number): Promise<Task> {
  const response = await fetch(`/api/tasks/${taskId}`)
  return parseResponse<Task>(response, 'Failed to load task')
}

export async function updateTaskStatus(
  taskId: number,
  payload: UpdateTaskStatusPayload
): Promise<Task> {
  const response = await fetch(`/api/tasks/${taskId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<Task>(response, 'Failed to update task status')
}

export async function getTaskProgress(taskId: number): Promise<TaskProgress> {
  const response = await fetch(`/api/status/tasks/${taskId}`)
  return parseResponse<TaskProgress>(response, 'Failed to load task progress')
}

export async function getDashboardStatus(): Promise<DashboardStatus> {
  const response = await fetch('/api/status/dashboard')
  return parseResponse<DashboardStatus>(response, 'Failed to load dashboard')
}

export async function listTaskFeedback(taskId: number): Promise<FeedbackEntry[]> {
  const response = await fetch(`/api/review/feedback/${taskId}`)
  return parseResponse<FeedbackEntry[]>(response, 'Failed to load feedback history')
}

export async function createExplicitFeedback(
  payload: CreateExplicitFeedbackPayload
): Promise<FeedbackEntry> {
  const response = await fetch('/api/review/feedback/explicit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<FeedbackEntry>(response, 'Failed to submit reviewer feedback')
}

export async function runChecker(payload: RunCheckerPayload): Promise<CheckerReport> {
  const response = await fetch('/api/review/checker/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<CheckerReport>(response, 'Failed to run checker')
}
