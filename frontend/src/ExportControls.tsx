import {useEffect,useRef,useState} from 'react'
import {sessionContextVersion} from './api'
import {downloadSavedExport} from './exportDownload'
export function ExportControls({dirty}:{dirty:boolean}) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('')
  const alive=useRef(true),request=useRef<AbortController|null>(null)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;request.current?.abort()}},[])
  async function download() {
    if (request.current) return
    const controller=new AbortController(),version=sessionContextVersion()
    request.current=controller;setBusy(true);setError('');setMessage('Preparing your saved data…')
    const active=()=>alive.current && version===sessionContextVersion()
    const timeout=setTimeout(()=>controller.abort(),30_000)
    try {
      await downloadSavedExport(controller.signal,active)
      if (active()) setMessage(controller.signal.aborted?'Export timed out. Try again.':'Download requested. Check your browser’s downloads for the JSON file.')
    } catch(err) {
      if (active()) {setMessage('');setError(controller.signal.aborted?'Export timed out. No file was downloaded; please retry.':(err as Error).message)}
    } finally {clearTimeout(timeout);request.current=null;if(alive.current)setBusy(false)}
  }
  return <details className="export-controls"><summary>Download your saved data</summary>
    <p>Download all your saved workspaces and historical reviews as JSON, including saved budgets, reasoning, and product source details.</p>
    <p className="hint">{dirty?'You have unsaved edits. Save them first if you want them in this export.':'Only data already saved to your account is included.'} Downloading never saves or changes a workspace. Keep the file private if it contains personal information.</p>
    <button type="button" disabled={busy} onClick={()=>void download()}>{busy?'Preparing download…':'Download saved data (.json)'}</button>
    {message&&<p className="hint" role="status">{message}</p>}{error&&<p className="error" role="alert">{error}</p>}
  </details>
}
