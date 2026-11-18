import {useState} from 'react'
import {storageRequest} from './api'
import type {SavedWorkspace} from './model'
export function DeleteWorkspace({saved,disabled}:{saved:SavedWorkspace;disabled:boolean}) {
  const [confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('')
  async function remove() {
    if(busy)return
    setBusy(true);setError('')
    try {
      await storageRequest<void>(`/decisions/${saved.id}`,'DELETE',{expected_revision:saved.revision,confirmation})
      window.location.assign(window.location.pathname)
    } catch(err) {setError((err as Error).message);setBusy(false)}
  }
  return <details><summary>Delete this saved workspace</summary><p>Permanently delete <strong>{saved.state.title}</strong> and all its saved reviews. Other workspaces and your account are kept.</p>
    <p>This action has no recovery window. Unsaved changes in this tab will also be cleared. Download your saved data first if you want a copy.</p>
    <label className="field"><span>Type DELETE to permanently delete this workspace</span><input value={confirmation} maxLength={10} autoComplete="off" onChange={e=>setConfirmation(e.target.value)}/></label>
    <button className="danger" type="button" disabled={disabled||busy||confirmation!=='DELETE'} onClick={()=>void remove()}>{busy?'Deleting…':'Permanently delete workspace'}</button>
    {error&&<p className="error" role="alert">{error}</p>}</details>
}
