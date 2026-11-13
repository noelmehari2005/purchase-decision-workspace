import { useState } from 'react'
import type { CandidateRecord, LaptopDraft, PurchasePlan } from './model'
import { candidateInput, money, planLabel } from './model'

export function TextField({label, value, onChange, hint, numeric = false, required = false}: {
  label: string; value: string; onChange: (value: string) => void; hint?: string; numeric?: boolean; required?: boolean;
}) {
  return <label className="field"><span>{label}</span><input value={value} onChange={e => onChange(e.target.value)}
    inputMode={numeric ? 'decimal' : undefined} maxLength={numeric ? 20 : 300} required={required} />
    {hint && <small>{hint}</small>}</label>
}

export function CandidateEditor({record, onEdit, onConfirm, onRemove}: {
  record: CandidateRecord; onEdit: (key: keyof LaptopDraft, value: string) => void;
  onConfirm: () => void; onRemove?: () => void;
}) {
  const [error, setError] = useState('')
  const d = record.draft
  const changed = record.confirmed !== null && JSON.stringify(d) !== JSON.stringify(record.confirmed)
  const edit = (key: keyof LaptopDraft, label: string, hint?: string, numeric = false) =>
    <TextField label={label} value={String(d[key])} hint={hint} numeric={numeric} onChange={value => {setError(''); onEdit(key, value)}} />
  function confirm() {
    try { candidateInput(d); setError(''); onConfirm() }
    catch (err) { setError((err as Error).message) }
  }
  return <article className="editor-card">
    <div className="section-heading"><div><span className="eyebrow">{d.current ? 'Your baseline' : 'Manual candidate'}</span>
      <h3>{d.name || 'New laptop'}</h3></div>
      <span className="badge">{!record.confirmed ? 'Draft' : changed ? 'Changes need review' : `Confirmed · revision ${record.revision}`}</span></div>
    <div className="field-grid">{edit('name', 'Product name')}{edit('configuration', 'Exact configuration', 'Model or part number, plus the particular build you mean.')}
      {edit('cpu', 'Processor (CPU)', 'Optional; leave unknown if you cannot find it.')}{edit('os', 'Operating system', 'Optional; include edition/version if known.')}
      {edit('ram', 'Installed RAM (GB)', 'Unknown? Leave blank.', true)}{edit('storage', 'Installed storage (GB)', 'Example: enter 1000 for a 1 TB marketed drive.', true)}
    </div>
    <label className="field"><span>Required-tool compatibility</span><select value={d.compatible} onChange={e => onEdit('compatible', e.target.value)}>
      <option value="unknown">I’m not sure</option><option value="yes">I have evidence that my required tools are supported</option>
      <option value="no">At least one required tool is not supported</option></select>
      <small>This records your evidence; it does not run a hardware check.</small></label>
    <details><summary>Portability, battery evidence, and source</summary><div className="field-grid">
      {edit('weight', 'Laptop weight (grams)', 'Use the selected configuration’s weight.', true)}
      {edit('battery', 'Reported battery runtime (minutes)', 'Optional; battery capacity in Wh is not runtime.', true)}
      {edit('batteryContext', 'Battery test conditions / source', 'Only matching, nonempty contexts support a direct runtime comparison.')}
      {edit('source', 'Product source link', 'Reference only in this milestone; no information is fetched.')}
    </div></details>
    {!d.current && <><label className="field"><span>Which cost should the plan use?</span><select value={d.costMode} onChange={e => onEdit('costMode', e.target.value)}>
      <option value="components">Sum purchase cost components</option><option value="provisional">Use my provisional total instead</option></select></label>
      <div className="field-grid">{edit('price', 'Item price ($)', 'Blank means unknown.', true)}{edit('tax', 'Estimated tax ($)', 'Enter 0 only if you mean zero.', true)}
      {edit('shipping', 'Shipping ($)', 'Blank means unknown.', true)}{edit('other', 'Other purchase costs ($)', undefined, true)}
      {d.costMode === 'provisional' && edit('provisional', 'Provisional total ($)', 'Replaces the component sum; not added to it.', true)}
      </div></>}
    <label className="field"><span>{d.current ? 'What works or causes difficulty?' : 'Evidence, questions, and notes'}</span>
      <textarea value={d.notes} onChange={e => onEdit('notes', e.target.value)} rows={3} maxLength={3000} /></label>
    {d.current && <p className="hint">Keeping this laptop has $0 new purchase cost in this example. Reported difficulties do not identify their cause.</p>}
    {changed && <p className="notice">Comparisons still use your last confirmed revision. Review and confirm these changes to update it.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    <div className="button-row"><button className="primary" type="button" onClick={confirm} disabled={!!record.confirmed && !changed}>
      {!record.confirmed ? 'Confirm reviewed laptop' : changed ? 'Confirm revised laptop' : 'Confirmed'}</button>
      {onRemove && <button className="quiet" type="button" onClick={onRemove}>Remove candidate</button>}</div>
  </article>
}

export function PlanSummary({plan, provisional, label}: {plan: PurchasePlan; provisional: boolean; label: string}) {
  return <div className="plan-summary"><strong>{label}</strong><p>{planLabel(plan)}</p>
    {plan.meets_target !== null && <small>{plan.meets_target ? 'Within' : 'Misses'} your target under these {provisional ? 'provisional ' : ''}assumptions.</small>}
    {plan.required_monthly_cents !== null && <p className="hint">Target needs {money(plan.required_monthly_cents)} per month.</p>}
    {plan.available_contributions === 0 && plan.status !== 'funded' && <p className="hint">No scheduled contribution occurs by your target date.</p>}
    {provisional && <small>Provisional total: this is an assumed timeline, not confirmed affordability.</small>}
  </div>
}
