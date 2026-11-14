import {useRef,useState} from 'react'
import {storageRequest,StorageRequestError} from './api'
import type {SessionStatus} from './session'

export function AccountLifecycle({status,onClosed}:{status:SessionStatus;onClosed:(message:string)=>void}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[reauth,setReauth]=useState(false)
  const requestId=useRef(crypto.randomUUID())
  const pending=status.account_state==='pending_deletion'
  async function run(restore=false) {
    if(busy)return
    setBusy(true);setError('');setReauth(false)
    try {
      if(restore) {
        await storageRequest('/account/restore','POST',{})
        window.location.assign('/')
      } else {
        const result=await storageRequest<{delete_after:number;notification_status:string}>('/account/deletion-request','POST',
          {request_id:requestId.current,confirmation})
        onClosed(`Account deletion requested. To recover your data, sign in and choose Restore account before ${new Date(result.delete_after*1000).toLocaleString()}. Signing in alone does not cancel deletion. A notification email is queued; delivery has not been confirmed.`)
      }
    } catch(err) {setError((err as Error).message);setReauth(err instanceof StorageRequestError&&err.code==='reauth_required')}
    finally {setBusy(false)}
  }
  if(pending) return <section className="account-recovery" aria-label="Account recovery"><h2>Your account is pending deletion</h2>
    <p>Recovery deadline: <strong>{status.delete_after?new Date(status.delete_after*1000).toLocaleString():'Unavailable'}</strong>.</p>
    <p>Your saved workspaces are closed. Signing in does not cancel deletion.</p>
    {status.can_restore?<button type="button" className="primary" disabled={busy} onClick={()=>void run(true)}>{busy?'Restoring…':'Restore account'}</button>:
      <p>The recovery window has ended. Your account cannot be restored.</p>}
    <p className="hint">Notification status: {status.notification_status==='sent'?'Sent':status.notification_status==='sending'?'Sending':'Queued; delivery not confirmed'}.</p>
    {error&&<p className="error" role="alert">{error}</p>}{reauth&&<a href="/api/v1/auth/login">Sign in again to continue</a>}
  </section>
  return <details className="account-deletion"><summary>Delete account</summary>
    <p>Start a 30-day recovery window for this account and all its saved workspaces and reviews. You will be signed out. Your data stays unavailable unless you sign in and explicitly restore the account before the deadline.</p>
    <p>After the recovery window, deletion is permanent. You can download your saved data before continuing.</p>
    {!status.notification_delivery_configured&&<p className="notice">Email delivery is not configured in this local build. A deletion notice will be queued, but will not be sent until delivery is configured and the maintenance job runs.</p>}
    <label className="field"><span>Type DELETE MY ACCOUNT to continue</span><input value={confirmation} maxLength={40} autoComplete="off" onChange={e=>setConfirmation(e.target.value)}/></label>
    <button className="danger" type="button" disabled={busy||confirmation!=='DELETE MY ACCOUNT'} onClick={()=>void run()}>{busy?'Requesting deletion…':'Start account deletion'}</button>
    {error&&<p className="error" role="alert">{error}</p>}{reauth&&<a href="/api/v1/auth/login">Sign in again to continue</a>}
  </details>
}
