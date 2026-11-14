/** A download is created only after the request succeeds for the same open account. */
import {StorageRequestError} from './api.ts'
export async function downloadSavedExport(signal:AbortSignal, active:()=>boolean):Promise<void> {
  const response=await fetch('/api/v1/account/export',{signal,cache:'no-store',credentials:'same-origin'})
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The export service did not return JSON. Check that the backend is running.')
  if (!response.ok) {
    const body=await response.json()
    if (response.status===401 || body.code==='email_unverified' || body.code==='account_restricted') window.dispatchEvent(new Event('pdw-auth-required'))
    throw new StorageRequestError(body.message||'Unable to prepare the export.',body.code||'export_failed')
  }
  const blob=await response.blob()
  if (signal.aborted || !active()) return
  const url=URL.createObjectURL(blob)
  const link=document.createElement('a')
  link.href=url;link.download='purchase-decision-workspace-export.json'
  try {document.body.appendChild(link);link.click()} finally {link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
}
