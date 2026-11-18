import {AccountLifecycle} from './AccountLifecycle'
import {setBearer} from './deployment'
import {useCallback,useEffect,useRef,useState} from 'react'
import App from './App'
import {setSessionContext,storageRequest,StorageRequestError} from './api'

import {privateAccess as hasPrivateAccess,sessionDeadline,workspaceIdentity,requiresSignIn} from './session'
import type {SessionStatus} from './session'

const loginPath=(signup=false)=>{
  const decision=new URLSearchParams(window.location.search).get('decision')
  return '/api/v1/auth/'+(signup?'signup':'login')+(decision?'?decision='+encodeURIComponent(decision):'')
}
function clearAddress() {
  const url=new URL(window.location.href)
  url.searchParams.delete('decision');url.searchParams.delete('auth_error')
  window.history.replaceState(null,'',url)
}
export default function AuthShell({hosted}:{hosted?:{login:(signup?:boolean)=>void;logout:()=>void}}={}) {
  const [status,setStatus]=useState<SessionStatus|null>(null)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState(new URLSearchParams(window.location.search).has('auth_error')?'Sign-in did not complete. Please try again.':'')
  const [email,setEmail]=useState('')
  const [busy,setBusy]=useState(false)
  const stateRef=useRef<SessionStatus|null>(null)
  const generation=useRef(0)
  const loading=useRef(false)
  const lastActivity=useRef(0)
  const apply=useCallback((next:SessionStatus)=>{
    const previous=stateRef.current
    if (previous?.authenticated && (!next.authenticated || previous.user?.id!==next.user?.id)) clearAddress()
    if (previous?.authenticated && previous.verified && !next.verified) clearAddress()
    if (next.account_state==='pending_deletion') clearAddress()
    if (!next.authenticated) setBearer(null)
    stateRef.current=next
    setSessionContext(next.mode==='auth0' && next.authenticated ? next.csrf || null : null)
    setStatus(next)
  },[])
  const refresh=useCallback(async()=>{
    if (loading.current) return
    loading.current=true
    const version=generation.current
    try {
      const next=await storageRequest<SessionStatus>('/auth/session')
      if (version===generation.current) {apply(next);setError('')}
    } catch(err) {
      if (version!==generation.current) return
      const current=stateRef.current
      // A restored credential is untrusted until this initial check succeeds.
      // Clear it on any failure, including provider outages or account denial.
      if (!current?.authenticated) setBearer(null)
      if (current?.authenticated) {
        clearAddress();apply({mode:'auth0',configured:current.configured,authenticated:false})
        setNotice('Your private workspace was closed. Saved records are unchanged; unsaved edits were cleared. Sign in to reopen your work.')
      }
      if (err instanceof StorageRequestError && requiresSignIn(err.code)) {
        clearAddress();apply({mode:'auth0',configured:true,authenticated:false})
        if (!current?.authenticated) setNotice(err.message)
        setError('')
        return
      }
      setError((err as Error).message)
    } finally {loading.current=false}
  },[apply])
  useEffect(()=>{
    void refresh()
    const timer=setInterval(()=>void refresh(),20_000)
    const focus=()=>{
      const current=stateRef.current
      if (current?.authenticated && Date.now()>=sessionDeadline(current)) {
        generation.current++;clearAddress();apply({mode:'auth0',configured:current.configured,authenticated:false})
        setNotice('Your session expired. Sign in again to reopen saved work.')
      }
      void refresh()
    }
    window.addEventListener('focus',focus);window.addEventListener('pageshow',focus)
    return ()=>{clearInterval(timer);window.removeEventListener('focus',focus);window.removeEventListener('pageshow',focus);generation.current++;loading.current=false}
  },[refresh,apply])
  useEffect(()=>{
    if (!status?.authenticated) return
    const until=sessionDeadline(status)
    const timeout=setTimeout(()=>{
      generation.current++;clearAddress();apply({mode:'auth0',configured:status.configured,authenticated:false})
      setNotice('Your session expired. Saved work is unchanged; unsaved edits were cleared. Sign in again to continue.')
    },Math.max(0,until-Date.now()))
    const active=()=>{
      if (Date.now()-lastActivity.current<60_000 || document.visibilityState!=='visible') return
      lastActivity.current=Date.now()
      const version=generation.current
      void storageRequest<{idle_until:number}>('/auth/activity','POST',{}).then(result=>{
        if (generation.current===version && stateRef.current?.authenticated)
          apply({...stateRef.current,idle_until:result.idle_until})
      }).catch(()=>void refresh())
    }
    window.addEventListener('pointerdown',active);window.addEventListener('keydown',active);window.addEventListener('scroll',active,{capture:true,passive:true})
    return ()=>{clearTimeout(timeout);window.removeEventListener('pointerdown',active);window.removeEventListener('keydown',active);window.removeEventListener('scroll',active,true)}
  },[status,apply,refresh])
  useEffect(()=>{
    const unauthorized=()=>void refresh()
    window.addEventListener('pdw-auth-required',unauthorized)
    return ()=>window.removeEventListener('pdw-auth-required',unauthorized)
  },[refresh])

  async function logout() {
    setBusy(true);setError('')
    try {
      await storageRequest('/auth/logout','POST',{})
      generation.current++;clearAddress();apply({mode:'auth0',configured:true,authenticated:false})
      setNotice('Signed out. Saved workspaces remain in your account; unsaved changes were cleared.')
      hosted?.logout()
    } catch(err) {setError((err as Error).message)} finally {setBusy(false)}
  }
  async function resetPassword(event:React.FormEvent) {
    event.preventDefault();setBusy(true);setError('')
    try {
      const result=await storageRequest<{message:string}>('/auth/password-reset','POST',{email})
      setNotice(result.message);setEmail('')
    } catch(err) {setError((err as Error).message)} finally {setBusy(false)}
  }
  const privateAccess=hasPrivateAccess(status)
  const allowed=status?.mode==='local' || privateAccess
  return <>
    <section className="account-panel" aria-label="Your account">
      <div className="section-heading"><div><strong>{status?.mode==='local'?'Local demonstration':privateAccess?'Your private workspace':'Try the laptop workspace'}</strong>
        <p className="hint">{status?.authenticated ? `${status.user?.email}${status.verified?' · Email verified':' · Verify your email before accessing saved workspaces.'}`:
          status?.mode==='local'?'Single-user prototype storage. No account is connected.':'Explore the fictional example without an account. Sign in to save your own decisions.'}</p></div>
        <div className="button-row">{status?.authenticated ? <>
          {!status.verified && <button type="button" onClick={()=>void refresh()}>I’ve verified my email</button>}
          <button type="button" disabled={busy} onClick={()=>void logout()}>Sign out</button>
        </> : status?.mode==='auth0' && <>{hosted?<><button disabled={!status.configured} onClick={()=>hosted.login()}>Sign in</button><button disabled={!status.configured} onClick={()=>hosted.login(true)}>Create account</button></>:<><a className="account-link" aria-disabled={!status.configured} href={status.configured?loginPath():undefined}>Sign in</a>
          <a className="account-link" aria-disabled={!status.configured} href={status.configured?loginPath(true):undefined}>Create account</a></>}</>}</div>
      </div>
      {status?.mode==='auth0' && !status.configured && <p className="hint">Email/password sign-in is being connected. The fictional demo is available now.</p>}
      {!status && !error && <p role="status">Checking your session…</p>}
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error} <button type="button" onClick={()=>void refresh()}>Check session again</button></p>}
      {status?.mode==='auth0' && status.configured && !status.authenticated && <details><summary>Forgot your password?</summary>
        <form onSubmit={event=>void resetPassword(event)}><label className="field"><span>Account email address</span><input type="email" required maxLength={320} value={email} onChange={e=>setEmail(e.target.value)}/></label>
          <button type="submit" disabled={busy}>Request password reset</button></form></details>}
      {status?.authenticated && status.verified && <AccountLifecycle key={status.csrf} status={status} onReauthenticate={hosted?()=>hosted.login():undefined} onRestored={hosted?()=>void refresh():undefined} onClosed={message=>{
        generation.current++;clearAddress();apply({mode:'auth0',configured:true,authenticated:false});setNotice(message);setError('')
      }}/>}
    </section>
    {status && status.account_state!=='pending_deletion' && <App key={workspaceIdentity(status)} storageAllowed={!!allowed} accountMode={status.mode}/>}
  </>
}
