import type { Evaluation } from './model'
import {apiUrl,transport,deployment} from './deployment.ts'

export async function requestEvaluation(payload: unknown, signal: AbortSignal): Promise<Evaluation> {
  const response = await fetch(apiUrl('/evaluations'), {
    credentials:transport().credentials,
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

let sessionCsrf:string|null=null
let contextVersion=0
export function sessionContextVersion() {return contextVersion}
export function setSessionContext(csrf:string|null) {if(sessionCsrf!==csrf)contextVersion++;sessionCsrf=csrf}

export class StorageRequestError extends Error {
  code: string
  constructor(message: string, code: string) {super(message); this.code = code}
}
export async function storageRequest<T>(path: string, method = 'GET', payload?: unknown): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), deployment().hosted?90_000:12_000)
  try {
    const options=transport()
    const response = await fetch(apiUrl(path), {method, signal:controller.signal,credentials:options.credentials,
      headers: {...options.headers,...(payload ? {'Content-Type':'application/json'} : {}),
        ...(method!=='GET' && sessionCsrf ? {'X-PDW-CSRF':sessionCsrf} : {})},
      body: payload ? JSON.stringify(payload) : undefined})
    if (response.status===204 && response.ok) return undefined as T
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Check that the local backend is running.')
    const data = await response.json()
    if (!response.ok) {
      if (path!=='/auth/session' && (response.status===401 || data.code==='email_unverified' || data.code==='account_restricted' || data.code==='tester_required'))
        window.dispatchEvent(new Event('pdw-auth-required'))
      throw new StorageRequestError(data.field_errors?.length ?
      data.field_errors.map((e: {path:string;message:string})=>`${e.path}: ${e.message}`).join(' ') : data.message || 'Storage request failed.', data.code)
    }
    return data as T
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Storage timed out. Your current tab remains unchanged; retry to check the saved record.')
    throw error
  } finally {clearTimeout(timeout)}
}
