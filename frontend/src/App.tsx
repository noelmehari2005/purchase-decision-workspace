import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {SourceEvidence} from './ImportPanel'
import { CandidateEditor, PlanSummary, TextField } from './components'
import { requestEvaluation } from './api'
import { WorkspaceStorage } from './WorkspaceStorage'
import { evaluationInput, initialRecords, money, newLaptop } from './model'
import type { CandidateRecord, CandidateResult, Evaluation, Group, Importance, LaptopDraft, PlanForm, RequirementForm, WorkspaceState } from './model'

const steps = ['Your needs', 'Current laptop', 'Candidates', 'Compare & plan', 'Your decision']
const taskLabels = ['Write and run basic programs', 'Build websites and web applications', 'Run a local backend and database',
  'Use Docker containers', 'Work in an IDE on larger projects', 'Use several development tools at once']
const groupNames: Record<Group, string> = {met: 'Meets your requirements', unknown: 'Needs verification',
  failed: 'Doesn’t meet your requirements', unset: 'No mandatory requirements set'}
const initialPlan: PlanForm = {savings: '300', contribution: '150', firstDate: '2027-01-31', targetDate: '2027-03-31',
  essential: false, useBudget: false, income: '1600', housing: '700', food: '250', transportation: '180',
  other: '120', goals: '150', buffer: '50', useScenario: false, category: 'transportation', reduction: '40', allocation: '40'}

function App({storageAllowed=true,accountMode='local'}:{storageAllowed?:boolean;accountMode?:'local'|'auth0'}) {
  const [step, setStep] = useState(0)
  const [editorEpoch,setEditorEpoch]=useState(0)
  const [title, setTitle] = useState('Alex’s laptop decision')
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Los_Angeles')
  const [restoring,setRestoring] = useState(storageAllowed && new URLSearchParams(window.location.search).has('decision'))
  const titleRef = useRef<HTMLHeadingElement>(null)
  const addCandidateRef=useRef<HTMLButtonElement>(null)
  const [focusCandidate,setFocusCandidate]=useState<string|null>(null)
  useEffect(()=>{if(focusCandidate)setFocusCandidate(null)},[focusCandidate])
  const [tasks, setTasks] = useState(taskLabels.map((name, i) => ({name, selected: i < 4,
    timing: i === 3 ? 'upcoming' : 'current', experience: i === 2 ? 'struggles' : i === 3 ? 'unknown' : 'adequate'})))
  const [customNeeds, setCustomNeeds] = useState('')
  const [requirements, setRequirements] = useState<RequirementForm>({ram: '16', storage: '512', ceiling: '900', noLimit: false, compatibility: true})
  const [preferences, setPreferences] = useState<Record<string, Importance>>({performance: 'high', portability: 'medium', battery: 'medium', repairability: 'low', cost: 'ignored'})
  const [records, setRecords] = useState<CandidateRecord[]>(initialRecords)
  const [plan, setPlan] = useState<PlanForm>(initialPlan)
  const [outcome, setOutcome] = useState('Investigate and save')
  const [reason, setReason] = useState('Confirm required-tool support and investigate the current laptop’s slowdown before committing.')
  const [response, setResponse] = useState<{key: string; data: Evaluation} | null>(null)
  const [apiError, setApiError] = useState<{key: string; message: string} | null>(null)
  const [retry, setRetry] = useState(0)
  const [review, setReview] = useState<{fingerprint: string; at: string} | null>(null)
  const request = useMemo(() => {
    try { return {json: JSON.stringify(evaluationInput(records, requirements, plan, preferences)), error: ''} }
    catch (error) { return {json: '', error: (error as Error).message} }
  }, [records, requirements, plan, preferences])
  useEffect(() => {
    if (!request.json) return
    const controller = new AbortController()
    let disposed = false
    let timeout: ReturnType<typeof setTimeout> | undefined
    const debounce = setTimeout(() => {
      timeout = setTimeout(() => controller.abort(), 10_000)
      requestEvaluation(JSON.parse(request.json), controller.signal)
        .then(data => {if (!disposed) {setResponse({key: request.json, data}); setApiError(null)}})
        .catch(error => {
          if (!disposed) setApiError({key: request.json, message: controller.signal.aborted ?
            'The calculation service timed out. Your inputs are still in this tab; try again.' :
            error instanceof TypeError ? 'Cannot reach the calculation service. Start the local FastAPI backend and retry.' : error.message})
        })
        .finally(() => clearTimeout(timeout))
    }, 250)
    return () => {disposed = true; clearTimeout(debounce); clearTimeout(timeout); controller.abort()}
  }, [request.json, retry])
  const evaluation = response?.key === request.json && !request.error ? response.data : null
  const error = request.error || (apiError?.key === request.json ? apiError.message : '')
  const confirmed = records.filter(r => r.confirmed)
  const fingerprint = JSON.stringify([request.json, tasks, customNeeds, confirmed.map(r => r.confirmed), evaluation?.versions, outcome, reason])
  const reviewCurrent = review?.fingerprint === fingerprint

  const workspace: WorkspaceState = useMemo(()=>({schemaVersion:1, title, timezone, tasks, customNeeds, requirements, preferences, records, plan, outcome, reason}),
    [title,timezone,tasks,customNeeds,requirements,preferences,records,plan,outcome,reason])
  const loadWorkspace = useCallback((state: WorkspaceState)=>{
    setFocusCandidate(null)
    setEditorEpoch(value=>value+1)
    setTitle(state.title); setTimezone(state.timezone); setTasks(state.tasks); setCustomNeeds(state.customNeeds)
    setRequirements(state.requirements); setPreferences(state.preferences); setRecords(state.records)
    setPlan(state.plan); setOutcome(state.outcome); setReason(state.reason); setReview(null); setResponse(null); setApiError(null)
  },[])
  const storageReady = useCallback(()=>setRestoring(false),[])

  function goTo(next: number) { setStep(next); requestAnimationFrame(() => titleRef.current?.focus()) }
  function editLaptop(id: string, key: keyof LaptopDraft, value: string) {
    setRecords(current => current.map(record => record.draft.id === id ? {...record, draft: {...record.draft, [key]: value}} : record))
  }
  function confirmLaptop(id: string) {
    setRecords(current => current.map(record => record.draft.id === id ?
      {...record, confirmed: {...record.draft}, revision: record.revision + 1} : record))
  }
  function editor(record: CandidateRecord) {
    return <CandidateEditor key={`${editorEpoch}:${record.draft.id}`} record={record} focusName={focusCandidate===record.draft.id}
      onImport={storageAllowed ? (before,next)=>setRecords(current=>current.map(r=>
        r.draft.id===before.id && JSON.stringify(r.draft)===JSON.stringify(before) ? {...r,draft:next}:r)) : undefined}
      onEdit={(key, value) => editLaptop(record.draft.id, key, value)} onConfirm={() => confirmLaptop(record.draft.id)}
      onRemove={record.draft.current ? undefined : () => {
        setRecords(current => current.filter(r => r.draft.id !== record.draft.id))
        if (outcome === record.draft.id) setOutcome('Undecided')
        requestAnimationFrame(()=>addCandidateRef.current?.focus())
      }} />
  }
  const requirementField = (key: 'ram' | 'storage' | 'ceiling', label: string) => <TextField label={label} numeric
    value={requirements[key]} onChange={value => setRequirements({...requirements, [key]: value})} />
  const planField = (key: keyof PlanForm, label: string, hint?: string) => <TextField label={label} numeric hint={hint}
    value={String(plan[key])} onChange={value => setPlan({...plan, [key]: value})} />

  function resultCard(record: CandidateRecord, result: CandidateResult) {
    const laptop = record.confirmed!
    const costScale = Math.max(120_000, ...evaluation!.candidates.map(row => row.cost_cents ?? 0))
    return <article className="result-card" key={laptop.id}>
      <div className="section-heading"><div><span className="eyebrow">{laptop.current ? 'Keep what you own' : `Confirmed revision ${record.revision}`}</span>
        <h3>{laptop.name}</h3><p className="hint">{laptop.configuration}</p></div>
        <span className={`badge ${result.group}`}>{groupNames[result.group]}</span></div>
      <div className="spec-grid"><div><small>CPU</small><span>{laptop.cpu || 'Unknown'}</span></div>
        <div><small>Installed RAM</small><span>{laptop.ram ? `${laptop.ram} GB` : 'Unknown'}</span></div>
        <div><small>Storage</small><span>{laptop.storage ? `${laptop.storage} GB` : 'Unknown'}</span></div>
        <div><small>Weight</small><span>{laptop.weight ? `${laptop.weight} g` : 'Unknown'}</span></div>
      </div>
      <div className="cost-display"><div className="section-heading"><strong>{money(result.cost_cents)}</strong>
        <small>{result.provisional ? 'Provisional total' : 'Entered purchase cost'}</small></div>
        {result.cost_cents !== null && <><div className="cost-track" role="img" aria-label={`Cost ${money(result.cost_cents)} on a zero to ${money(costScale)} scale`}>
          <span style={{width: `${result.cost_cents / costScale * 100}%`}} /></div><small>Same $0–{money(costScale)} scale for every option.</small></>}
      </div>
      <details><summary>Requirements and evidence</summary>{result.checks.length ? <ul className="check-list">{result.checks.map(check =>
        <li key={check.label}><strong>{check.status === 'met' ? 'Met' : check.status === 'failed' ? 'Not met' : 'Unknown'} · {check.label}</strong><p>{check.reason}</p></li>)}</ul> :
        <p>No mandatory checks were selected. This is not confirmation of technical suitability.</p>}
        <p>Battery runtime: {laptop.battery ? `${laptop.battery} minutes` : 'Unknown'}{laptop.batteryContext ? ` · ${laptop.batteryContext}` : ' · No comparable test context entered.'}</p>
        <p>Performance and repairability: {laptop.notes || 'No supporting evidence entered.'}</p>
        {laptop.source && <p className="source-text">Source: <a href={laptop.source} target="_blank" rel="noreferrer">{laptop.source}</a></p>}
        <SourceEvidence draft={laptop}/>
        <p className="hint">Confirmed by you; review confirmation does not independently validate the source or diagnose the device.</p>
      </details>
      {result.advantages.length > 0 && <ul className="advantages">{result.advantages.map(text => <li key={text}>{text}</li>)}</ul>}
      <div className="plan-grid"><PlanSummary label="Original plan" plan={result.base_plan} provisional={result.provisional} />
        {result.scenario_plan && <PlanSummary label="Your spending-change scenario" plan={result.scenario_plan} provisional={result.provisional} />}</div>
      {result.suggested_contribution_cents !== null && <p className="notice">Suggested starting contribution: <strong>{money(result.suggested_contribution_cents)} / month</strong>, bounded by your entered budget and buffer. Your chosen contribution remains {money(Number(plan.contribution) * 100)}.</p>}
      {result.group === 'met' && result.base_plan.meets_target === true && !result.provisional && <p className="fit">Meets your entered requirements and original-plan target under the stated assumptions.</p>}
      {plan.essential && result.base_plan.meets_target === false && <p className="notice">Your essential deadline is unmet by the original plan; technical eligibility is shown separately.</p>}
    </article>
  }

  return <div className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="app-header"><a className="brand" href="#workspace"><span className="brand-mark" aria-hidden="true">P</span>
      <span>Purchase Decision<br /><strong>Workspace</strong></span></a><span className="local-label"><span aria-hidden="true" />Local prototype · USD</span></header>
    <div className="workspace-layout"><aside className="sidebar"><p className="eyebrow">Your laptop decision</p>
      <nav aria-label="Decision steps">{steps.map((label, index) => <button key={label} type="button" aria-current={index === step ? 'step' : undefined} onClick={() => goTo(index)}>
        <span className="step-number" aria-hidden="true">{index + 1}</span>{label}</button>)}</nav>
      <div className="sidebar-note"><strong>Your choice, explained.</strong><p>Keep the laptop you own, investigate a gap, or plan a replacement.</p></div>
    </aside><main id="workspace" tabIndex={-1}>
      <div className="page-heading"><span className="eyebrow">Step {step + 1} of {steps.length}</span>
        <h1 ref={titleRef} tabIndex={-1}>{steps[step]}</h1><p>{[
          'Start with what you need to do, not a hardware score.', 'Understand what works before deciding to replace it.',
          'Add exact configurations. Review each laptop before comparing.', 'Separate suitability, tradeoffs, and purchase timing.',
          'Capture your reasoning, including what remains uncertain.',
        ][step]}</p></div>
      <div className="prototype-note">Alex’s fictional example is prefilled. Review the example and change it to explore your needs. Saving is always explicit. Unsaved changes are lost on reload or sign-out.</div>

      {storageAllowed && <WorkspaceStorage accountMode={accountMode} state={workspace} onLoad={loadWorkspace} onReady={storageReady} onTitle={setTitle} onTimezone={setTimezone}/> }
      {!storageAllowed && <p className="notice">Fictional demo · changes stay in this tab. Sign in with a verified email to save a private workspace.</p>}
      {restoring && <p role="status" className="notice">Restoring your saved workspace…</p>}
      <div inert={restoring}>
      {step === 0 && <>
        <section className="surface"><h2>Programming tasks</h2><p>Select tasks and describe your current experience. Choosing a task doesn’t automatically create hardware requirements.</p>
          {tasks.map((task, index) => <div className="task-row" key={task.name}>
            <label className="check"><input type="checkbox" checked={task.selected} onChange={e => setTasks(tasks.map((t, i) => i === index ? {...t, selected: e.target.checked} : t))} />{task.name}</label>
            <label className="field"><span>When needed · {task.name}</span><select value={task.timing} disabled={!task.selected} onChange={e => setTasks(tasks.map((t,i) => i === index ? {...t,timing:e.target.value} : t))}>
              <option value="current">Now</option><option value="upcoming">Upcoming</option></select></label>
            <label className="field"><span>Current experience · {task.name}</span><select value={task.experience} disabled={!task.selected} onChange={e => setTasks(tasks.map((t,i) => i === index ? {...t,experience:e.target.value} : t))}>
              <option value="adequate">Works adequately</option><option value="struggles">Struggles</option><option value="cannot">Cannot run</option><option value="unknown">I’m not sure</option></select></label>
          </div>)}
          <label className="field"><span>Other needs, required tools, or upcoming dates</span><textarea value={customNeeds} onChange={e => setCustomNeeds(e.target.value)} maxLength={3000} rows={3} /></label>
        </section>
        <section className="surface"><h2>Your mandatory requirements</h2><p>These are your choices. Blank minimums mean no requirement; unknown candidate values remain unconfirmed.</p>
          <div className="field-grid">{requirementField('ram', 'Minimum installed RAM (GB)')}{requirementField('storage', 'Minimum installed storage (GB)')}
            {!requirements.noLimit && requirementField('ceiling', 'Maximum total purchase price ($)')}</div>
          <label className="check"><input type="checkbox" checked={requirements.noLimit} onChange={e => setRequirements({...requirements, noLimit: e.target.checked})} />No price limit</label>
          <label className="check"><input type="checkbox" checked={requirements.compatibility} onChange={e => setRequirements({...requirements, compatibility: e.target.checked})} />Require evidence of support for my required tools</label>
        </section>
        <section className="surface"><h2>What matters to you?</h2><p>Importance guides the explained tradeoffs. No combined score or universal winner is assigned.</p><div className="field-grid">
          {Object.entries({performance:'Performance for my workload', portability:'Portability', battery:'Battery runtime', repairability:'Repairability / upgrades', cost:'Lower purchase cost'}).map(([key,label]) =>
            <label className="field" key={key}><span>{label}</span><select value={preferences[key]} onChange={e => setPreferences({...preferences, [key]:e.target.value as Importance})}>
              <option value="high">High importance</option><option value="medium">Medium importance</option><option value="low">Low importance</option><option value="ignored">Ignore</option></select></label>)}
        </div><p className="hint">Performance and repairability remain evidence notes in this milestone. Weight and matching battery measurements can support direct tradeoffs; missing evidence never becomes a zero score.</p></section>
      </>}
      {step === 1 && <>{editor(records[0])}<p className="hint">“I’m not sure” is always valid. Missing details leave related requirements unconfirmed. The app does not automatically inspect your device.</p></>}
      {step === 2 && <><div className="notice">Add a laptop below, then import its specifications from Icecat or enter them manually. Review and confirm each draft before comparing.</div>
        {!storageAllowed && <p className="hint">Sign in with a verified email to use Icecat importing. Manual entry works in this demo.</p>}
        {records.filter(r => !r.draft.current).map(editor)}
        <button ref={addCandidateRef} type="button" className="secondary" disabled={records.length >= 20} onClick={()=>{
          const draft=newLaptop(crypto.randomUUID());setRecords([...records,{draft,confirmed:null,revision:0}]);setFocusCandidate(draft.id)
        }}>+ Add another laptop</button>
        <p className="hint">{records.length - 1} replacement drafts · maximum 19 in this local workspace. Only confirmed revisions enter comparison.</p>
      </>}
      {step === 3 && <>
        <section className="surface"><h2>Choose your contribution</h2><p>Purchase savings exclude money you intend to protect. Dates repeat monthly from your original chosen day.</p>
          <div className="field-grid">{planField('savings','Savings set aside for this purchase ($)')}{planField('contribution','Your chosen monthly contribution ($)')}
            <label className="field"><span>First contribution date</span><input type="date" value={plan.firstDate} onChange={e => setPlan({...plan, firstDate:e.target.value})} /></label>
            <label className="field"><span>Target purchase date (optional)</span><input type="date" value={plan.targetDate} onChange={e => setPlan({...plan, targetDate:e.target.value})} /></label></div>
          <label className="check"><input type="checkbox" checked={plan.essential} onChange={e => setPlan({...plan,essential:e.target.checked})} />This deadline is essential</label>
          <label className="check"><input type="checkbox" checked={plan.useBudget} onChange={e => setPlan({...plan,useBudget:e.target.checked,useScenario:e.target.checked ? plan.useScenario : false})} />Include an optional monthly budget</label>
          {plan.useBudget && <div className="budget-area"><h3>Monthly budget</h3><p className="hint">Blank means unknown. Enter zero explicitly where appropriate. Don’t count other goals or your buffer again as expenses.</p>
            <div className="field-grid">{planField('income','Take-home income ($)')}{planField('housing','Housing ($)')}{planField('food','Food ($)')}
              {planField('transportation','Transportation ($)')}{planField('other','Other expenses / commitments ($)')}{planField('goals','Reserved for other goals ($)')}{planField('buffer','Extra amount to leave unallocated ($)')}
            </div><label className="check"><input type="checkbox" checked={plan.useScenario} onChange={e => setPlan({...plan,useScenario:e.target.checked})} />Explore one spending-change scenario</label>
            {plan.useScenario && <div className="scenario-area"><h3>Your optional change</h3><label className="field"><span>Expense category</span><select value={plan.category} onChange={e => setPlan({...plan,category:e.target.value})}>
              <option value="housing">Housing</option><option value="food">Food</option><option value="transportation">Transportation</option><option value="other">Other expenses</option></select></label>
              <div className="field-grid">{planField('reduction','Possible monthly reduction ($)')}{planField('allocation','Amount of that reduction toward purchase ($)')}</div>
              <p className="hint">You decide if the change is practical. The original budget stays unchanged.</p></div>}
          </div>}
        </section>
        <section aria-label="Evaluation status" aria-live="polite">
          {error ? <div className="error" role="alert">{error}{!request.error && <button type="button" onClick={() => {setApiError(null); setRetry(retry+1)}}>Retry calculation</button>}</div> :
            !evaluation ? <p className="notice">Updating your comparison…</p> : <>
              {plan.useBudget && <p className="notice">Remaining after entered commitments and buffer: <strong>{money(evaluation.budget_capacity_cents)} / month</strong>. This is not a recommendation to use it all.</p>}
              {evaluation.warnings.map(text => <p className="notice" key={text}>{text}</p>)}
              {confirmed.length === 0 && <p className="notice">No laptops confirmed yet. Review the current laptop and candidate drafts before comparing.</p>}
              {records.some(r => !r.confirmed) && <p className="hint">Unconfirmed drafts are excluded. Confirm them in Current laptop or Candidates.</p>}
            </>}
        </section>
        {evaluation && <div className="comparison-groups">{(['met','unknown','failed','unset'] as Group[]).map(group => {
          const rows = evaluation.candidates.filter(row => row.group === group && !records.find(r => r.draft.id === row.id)?.draft.current)
          if (group === 'unset' && !rows.length) return null
          return <section key={group} className="comparison-section"><div className="section-heading"><h2>{groupNames[group]}</h2><span className="count">{rows.length}</span></div>
            {rows.length ? rows.map(row => resultCard(records.find(r => r.draft.id === row.id)!,row)) : <p className="empty">No confirmed replacements in this group.</p>}</section>
        })}
          {evaluation.candidates.filter(row => records.find(r => r.draft.id === row.id)?.draft.current).map(row =>
            <section className="comparison-section" key={row.id}><h2>Current laptop baseline</h2>{resultCard(records[0],row)}</section>)}
        </div>}
        <p className="hint">Timelines assume unchanged costs and equal monthly contributions. No interest, financing, future discounts, or performance guarantees are modeled.</p>
      </>}
      {step === 4 && <section className="surface"><h2>Your decision can stay open</h2><label className="field"><span>Current direction</span><select value={outcome} onChange={e => setOutcome(e.target.value)}>
        <option>Investigate and save</option><option>Keep my current laptop</option><option>Undecided</option>
        {confirmed.filter(r=>!r.draft.current).map(record=><option key={record.draft.id} value={record.draft.id}>Plan for {record.confirmed!.name}</option>)}</select></label>
        <label className="field"><span>Your reasoning and next steps</span><textarea rows={4} value={reason} onChange={e => setReason(e.target.value)} maxLength={4000} /></label>
        <h3>Before committing to a purchase</h3><ul><li>Review unconfirmed requirements and missing source evidence.</li><li>Revisit cost estimates, dates, income, and expenses when circumstances change.</li><li>Investigate reported current-laptop difficulties without assuming their cause.</li></ul>
        {evaluation && <div className="review-summary"><p>{confirmed.length} confirmed laptop revisions · {money(Number(plan.contribution)*100)} chosen monthly contribution.</p>
          <p className="hint">Model versions: {Object.entries(evaluation.versions).map(([key,value])=>`${key} ${value}`).join(' · ')}</p></div>}
        {error && <p className="error" role="alert">Resolve the plan error before capturing a local review: {error}</p>}
        <button type="button" className="primary" disabled={!evaluation || !confirmed.length} onClick={() => setReview({fingerprint,at:new Date().toLocaleString()})}>Preview review in this tab</button>
        <p role="status" className="notice">{reviewCurrent ? `Local review captured at ${review!.at}. This preview will be lost on reload. Use Decision history above for a saved review.` :
          review ? 'Your inputs changed since the last local review. Capture it again when ready.' : 'This preview remains in the current tab. Save your workspace, then use Decision history above to preserve a review.'}</p>
      </section>}
      </div>
      <footer className="step-footer"><button type="button" disabled={step === 0} onClick={() => goTo(step-1)}>Back</button><span>{step+1} / {steps.length}</span>
        {step < steps.length-1 && <button className="primary" type="button" onClick={() => goTo(step+1)}>Continue <span aria-hidden="true">→</span></button>}</footer>
    </main></div>
  </div>
}
export default App
