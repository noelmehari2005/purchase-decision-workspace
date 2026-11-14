import {SourceEvidence} from './ImportPanel'
import {useEffect, useRef, useState} from 'react'
import {storageRequest} from './api'
import {money} from './model'
import type {SavedReview, SavedWorkspace, WorkspaceState} from './model'
import {PlanSummary, TextField} from './components'

type Summary = {id:string; title:string; revision:number; updated_at:string}
type ReviewSummary = {id:string; title:string; decision_revision:number; created_at:string}
const initialId = () => new URLSearchParams(window.location.search).get('decision')
const address = (id:string) => {
  const url = new URL(window.location.href)
  url.searchParams.set('decision',id)
  window.history.replaceState(null,'',url)
}
export function WorkspaceStorage({state,onLoad,onReady,onTitle,onTimezone,accountMode}: {
  accountMode:'local'|'auth0';
  state:WorkspaceState; onLoad:(state:WorkspaceState)=>void; onReady:()=>void;
  onTitle:(title:string)=>void; onTimezone:(timezone:string)=>void;
}) {
  const [saved,setSaved] = useState<SavedWorkspace|null>(null)
  const [items,setItems] = useState<Summary[]>([])
  const [reviews,setReviews] = useState<ReviewSummary[]>([])
  const [selected,setSelected] = useState('')
  const [offset,setOffset] = useState(0)
  const [historyOffset,setHistoryOffset] = useState(0)
  const [busy,setBusy] = useState(false)
  const [initializing,setInitializing] = useState(true)
  const latestState = useRef(state)
  latestState.current = state
  const copyRequest = useRef<string|null>(null)
  const [message,setMessage] = useState('Checking local saved workspaces…')
  const [error,setError] = useState('')
  const [historical,setHistorical] = useState<SavedReview|null>(null)
  const createId = useRef(crypto.randomUUID())
  const snapshotRequest = useRef<{revision:number;id:string}|null>(null)
  const callbacks = useRef({onLoad,onReady})
  callbacks.current = {onLoad,onReady}
  const dirty = !saved || JSON.stringify(saved.state) !== JSON.stringify(state)

  useEffect(()=>{
    let disposed = false
    async function start() {
      try {
        const list = await storageRequest<{items:Summary[]}>('/decisions')
        if (disposed) return
        setItems(list.items)
        const id = initialId()
        if (id) {
          const record = await storageRequest<SavedWorkspace>(`/decisions/${encodeURIComponent(id)}`)
          if (disposed) return
          callbacks.current.onLoad(record.state); setSaved(record); setSelected(record.id)
          setMessage(`Opened saved revision ${record.revision}.`)
        } else setMessage('Local storage connected. Save your workspace when ready.')
      } catch (err) {if (!disposed) {setError((err as Error).message); setMessage('Your edits are not saved automatically.')}}
      finally {if (!disposed) {setInitializing(false); callbacks.current.onReady()}}
    }
    void start()
    return ()=>{disposed=true}
  },[])

  useEffect(()=>{
    let disposed=false
    if (!saved) {setReviews([]); return}
    storageRequest<{items:ReviewSummary[]}>(`/decisions/${saved.id}/snapshots?offset=${historyOffset}&limit=10`)
      .then(data=>{if (!disposed) setReviews(data.items)})
      .catch(err=>{if (!disposed) setError(err.message)})
    return ()=>{disposed=true}
  },[saved,historyOffset])

  async function run(action:()=>Promise<void>) {
    if (busy) return
    setBusy(true); setError('')
    try {await action()} catch(err) {setError((err as Error).message)} finally {setBusy(false)}
  }
  async function save(asCopy=false) {
    if (asCopy && !copyRequest.current) copyRequest.current=crypto.randomUUID()
    const copy = asCopy ? copyRequest.current! : createId.current
    const captured = structuredClone(state)
    const record = saved && !asCopy ? await storageRequest<SavedWorkspace>(`/decisions/${saved.id}`,'PATCH',
      {expected_revision:saved.revision,state:captured}) : await storageRequest<SavedWorkspace>('/decisions','POST',
      {request_id:copy,state:captured})
    copyRequest.current=null
    setSaved(record); setSelected(record.id); address(record.id); setHistoryOffset(0); setHistorical(null)
    setMessage(`Saved workspace revision ${record.revision}. Changes made while saving still need another save.`)
    // Do not replace current inputs: edits made during the request must survive.
    const list = await storageRequest<{items:Summary[]}>(`/decisions?offset=${offset}&limit=10`)
    setItems(list.items)
    return record
  }
  async function open() {
    if (!selected) return
    const before=JSON.stringify(latestState.current)
    const record = await storageRequest<SavedWorkspace>(`/decisions/${selected}`)
    if (before !== JSON.stringify(latestState.current)) throw new Error('Inputs changed while opening the saved workspace. Review those changes, then open it again.')
    onLoad(record.state); setSaved(record); address(record.id); setHistorical(null); setHistoryOffset(0)
    setMessage(`Opened saved revision ${record.revision}.`)
  }
  async function page(next:number) {
    const list = await storageRequest<{items:Summary[]}>(`/decisions?offset=${next}&limit=10`)
    setItems(list.items); setOffset(next)
  }
  async function capture() {
    if (!saved || dirty) throw new Error('Save your current workspace changes before capturing a review.')
    if (!snapshotRequest.current || snapshotRequest.current.revision !== saved.revision)
      snapshotRequest.current = {revision:saved.revision,id:crypto.randomUUID()}
    const snapshot = await storageRequest<SavedReview>(`/decisions/${saved.id}/snapshots`,'POST',
      {expected_revision:saved.revision,request_id:snapshotRequest.current.id})
    setHistorical(snapshot); setHistoryOffset(0)
    const list = await storageRequest<{items:ReviewSummary[]}>(`/decisions/${saved.id}/snapshots?offset=0&limit=10`)
    setReviews(list.items); setMessage(`Saved a historical review of revision ${snapshot.decision_revision}.`)
  }
  return <section className="surface workspace-storage" aria-label="Saved workspace">
    <h2>Your saved workspace</h2>
    <fieldset className="storage-controls" disabled={initializing}>
    <p className="hint">{accountMode==='local'?'Local single-user demonstration. Use fictional data.':'Saved workspaces belong to your signed-in account.'} Save changes explicitly; unsaved edits are lost on reload or sign-out.</p>
    <div className="field-grid"><TextField label="Workspace title" value={state.title} onChange={onTitle}/>
      <TextField label="Calendar timezone" value={state.timezone} onChange={onTimezone} hint="IANA name, for example America/Los_Angeles. Contribution dates are local calendar dates."/></div>
    <div className="button-row"><button className="primary" type="button" disabled={busy || !dirty} onClick={()=>void run(async()=>{await save()})}>{busy?'Working…':saved?'Save changes':'Save workspace'}</button>
      {saved && <button type="button" disabled={busy} onClick={()=>void run(async()=>{await save(true)})}>Save as a new workspace</button>}
      <span className="hint">{saved ? `Revision ${saved.revision} · ${dirty?'Unsaved changes':'All changes saved'}`:'Not saved yet'}</span></div>
    <p className="hint" role="status">{message}</p>
    {error && <p role="alert" className="error">{error} Your current inputs remain in this tab. You can save as a new workspace if another tab changed this one.</p>}
    <details><summary>Open a saved workspace</summary>
      <label className="field"><span>Saved workspaces</span><select disabled={busy} value={selected} onChange={e=>setSelected(e.target.value)}>
        <option value="">Choose a workspace</option>{items.map(item=><option key={item.id} value={item.id}>{item.title} · revision {item.revision}</option>)}
      </select></label><div className="button-row"><button type="button" disabled={busy || !selected} onClick={()=>void run(open)}>
        {dirty?'Open selected and discard unsaved edits':'Open selected workspace'}</button>
        <button type="button" disabled={busy} onClick={()=>void run(()=>page(offset))}>Refresh list</button>
        <button type="button" disabled={busy || offset===0} onClick={()=>void run(()=>page(Math.max(0,offset-10)))}>Previous workspaces</button>
        <button type="button" disabled={busy || items.length<10} onClick={()=>void run(()=>page(offset+10))}>More workspaces</button></div>
    </details>
    {saved && <details><summary>Decision history</summary><p className="hint">Saved reviews freeze the saved workspace revision and server-calculated results. Future edits do not change them.</p>
      <button type="button" disabled={busy || dirty} onClick={()=>void run(capture)}>Save review to history</button>
      {dirty && <p className="hint">Save workspace changes first to capture that exact revision.</p>}
      {!reviews.length && <p className="hint">No saved reviews on this page.</p>}
      <ul>{reviews.map(review=><li key={review.id}><button className="quiet" type="button" disabled={busy} onClick={()=>void run(async()=>{
        const result=await storageRequest<SavedReview>(`/decisions/${saved.id}/snapshots/${review.id}`);setHistorical(result)
      })}>View revision {review.decision_revision} · {new Date(review.created_at).toLocaleString()}</button></li>)}</ul>
      <div className="button-row"><button type="button" disabled={busy || historyOffset===0} onClick={()=>setHistoryOffset(Math.max(0,historyOffset-10))}>Newer reviews</button>
        <button type="button" disabled={busy || reviews.length<10} onClick={()=>setHistoryOffset(historyOffset+10)}>Older reviews</button></div>
    </details>}
    {historical && <HistoricalReview snapshot={historical} onClose={()=>setHistorical(null)}/>}
    </fieldset>
  </section>
}

function HistoricalReview({snapshot,onClose}:{snapshot:SavedReview;onClose:()=>void}) {
  const state=snapshot.state
  const chosen=state.records.find(r=>r.confirmed?.id===state.outcome)?.confirmed?.name || state.outcome
  return <section className="historical-review" aria-label="Historical review"><div className="section-heading"><h2>Saved review · revision {snapshot.decision_revision}</h2>
    <button type="button" onClick={onClose}>Close review</button></div>
    <p><strong>{state.title}</strong> · {new Date(snapshot.created_at).toLocaleString()}</p>
    <p className="hint">Read-only history. These are saved results, not a recalculation using today's inputs.</p>
    <p>Direction: {chosen}</p><p className="preserve-lines">Reasoning: {state.reason || 'No reasoning entered.'}</p>
    <details><summary>Saved needs and planning assumptions</summary><ul>{state.tasks.filter(t=>t.selected).map((t,i)=><li key={i}>{t.name} · {t.timing} · {t.experience}</li>)}</ul>
      <p>{state.customNeeds || 'No additional needs entered.'}</p>
      <p>Minimum RAM: {state.requirements.ram || 'None'} GB · Storage: {state.requirements.storage || 'None'} GB · Price limit: {state.requirements.noLimit?'None':state.requirements.ceiling ? `$${state.requirements.ceiling}` : 'None'}.</p>
      <p>Savings: ${state.plan.savings} · Monthly contribution: ${state.plan.contribution} · First contribution: {state.plan.firstDate} · Target: {state.plan.targetDate || 'None'} · Timezone: {state.timezone}.</p>
      <p>Budget capacity after entered commitments and buffer: {money(snapshot.evaluation.budget_capacity_cents)}.</p>
    </details>
    {snapshot.evaluation.warnings.map(text=><p className="notice" key={text}>{text}</p>)}
    {snapshot.evaluation.candidates.map(row=>{
      const record=state.records.find(r=>r.confirmed?.id===row.id)!
      const laptop=record.confirmed!
      return <article className="result-card" key={row.id}><h3>{laptop.name} · candidate revision {record.revision}</h3><p>{laptop.configuration}</p>
        <p>{money(row.cost_cents)}{row.provisional?' · provisional':''}</p>
        <p>RAM: {laptop.ram || 'Unknown'} GB · Storage: {laptop.storage || 'Unknown'} GB · CPU: {laptop.cpu || 'Unknown'}</p>
        <ul>{row.checks.map(check=><li key={check.label}>{check.label}: {check.status}. {check.reason}</li>)}</ul>
        <div className="plan-grid"><PlanSummary label="Saved original plan" plan={row.base_plan} provisional={row.provisional}/>
          {row.scenario_plan && <PlanSummary label="Saved alternative plan" plan={row.scenario_plan} provisional={row.provisional}/>}</div>
        <SourceEvidence draft={laptop}/>
        {laptop.source && <p className="source-text">Recorded source: <a href={laptop.source} target="_blank" rel="noreferrer">{laptop.source}</a></p>}
      </article>
    })}
    <p className="hint">Saved model versions: {Object.entries(snapshot.evaluation.versions).map(([k,v])=>`${k} ${v}`).join(' · ')}</p>
  </section>
}
