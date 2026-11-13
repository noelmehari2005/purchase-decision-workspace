import type { Evaluation } from './model'

export async function requestEvaluation(payload: unknown, signal: AbortSignal): Promise<Evaluation> {
  const response = await fetch('/api/v1/evaluations', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal,
  })
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('The calculation service did not return a valid response. Check that the local backend is running.')
  const body = await response.json()
  if (!response.ok) {
    const details = body.field_errors?.map((item: {path: string; message: string}) => `${item.path}: ${item.message}`).join(' ')
    throw new Error(details || body.message || 'Unable to evaluate these inputs.')
  }
  return body as Evaluation
}

export class StorageRequestError extends Error {
  code: string
  constructor(message: string, code: string) {super(message); this.code = code}
}
export async function storageRequest<T>(path: string, method = 'GET', payload?: unknown): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 12_000)
  try {
    const response = await fetch(`/api/v1${path}`, {method, signal:controller.signal,
      headers: payload ? {'Content-Type':'application/json'} : undefined,
      body: payload ? JSON.stringify(payload) : undefined})
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Check that the local backend is running.')
    const data = await response.json()
    if (!response.ok) throw new StorageRequestError(data.field_errors?.length ?
      data.field_errors.map((e: {path:string;message:string})=>`${e.path}: ${e.message}`).join(' ') : data.message || 'Storage request failed.', data.code)
    return data as T
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Storage timed out. Your current tab remains unchanged; retry to check the saved record.')
    throw error
  } finally {clearTimeout(timeout)}
}
