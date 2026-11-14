import {useEffect,useRef,useState} from 'react'
import {storageRequest} from './api'
import type {LaptopDraft} from './model'
import {applyImport,retainedCorrections,sameProduct,specKeys,specLabels} from './imports'
import type {ImportEvidence,SpecKey} from './imports'
export function ImportPanel({draft,onApply}:{draft:LaptopDraft;onApply:(before:LaptopDraft,next:LaptopDraft)=>void}) {
  const [mode,setMode]=useState<'link'|'id'|'mpn'>('link'),[value,setValue]=useState(''),[brand,setBrand]=useState(''),[mpn,setMpn]=useState('')
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const [preview,setPreview]=useState<{evidence:ImportEvidence;before:LaptopDraft}|null>(null),[keep,setKeep]=useState<SpecKey[]>([])
  const alive=useRef(true), requestId=useRef<{key:string;id:string}|null>(null)
  useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
  async function fetchPreview() {
    if (busy) return
    setBusy(true);setError('');setPreview(null)
    const captured=structuredClone(draft),key=JSON.stringify({mode,value,brand,mpn})
    if (requestId.current?.key!==key) requestId.current={key,id:crypto.randomUUID()}
    try {
      const evidence=await storageRequest<ImportEvidence>('/imports/preview','POST',{request_id:requestId.current.id,mode,value,brand,mpn})
      if (!alive.current) return
      setPreview({evidence,before:captured});setKeep(retainedCorrections(captured,evidence))
    } catch(err) {if(alive.current)setError((err as Error).message)} finally {if(alive.current)setBusy(false)}
  }
  const stale=preview&&JSON.stringify(preview.before)!==JSON.stringify(draft)
  return <details className="import-panel"><summary>{draft.evidence?'Refresh or replace from Icecat':'Import specifications from Icecat'}</summary>
    <p>Use a product link or exact part number. Review the result before applying it to this draft.</p>
    <label className="field"><span>Find product by</span><select disabled={busy} value={mode} onChange={e=>{setMode(e.target.value as typeof mode);setValue('');setPreview(null)}}>
      <option value="link">Icecat product link</option><option value="id">Icecat product ID</option><option value="mpn">Brand and manufacturer part number</option></select></label>
    {mode==='mpn'?<div className="field-grid"><label className="field"><span>Brand</span><input value={brand} maxLength={100} disabled={busy} onChange={e=>{setBrand(e.target.value);setPreview(null)}}/></label>
      <label className="field"><span>Exact manufacturer part number</span><input value={mpn} maxLength={200} disabled={busy} onChange={e=>{setMpn(e.target.value);setPreview(null)}} placeholder="Include regional suffix, if present"/></label></div>:
      <label className="field"><span>{mode==='link'?'Icecat product URL':'Icecat ID'}</span><input value={value} maxLength={2000} disabled={busy} onChange={e=>{setValue(e.target.value);setPreview(null)}}/></label>}
    <button type="button" disabled={busy||(mode==='mpn'?!brand.trim()||!mpn.trim():!value.trim())} onClick={()=>void fetchPreview()}>{busy?'Fetching specifications…':'Fetch product for review'}</button>
    {busy&&<p role="status">Fetching one product. Your current laptop details are unchanged.</p>}
    {error&&<p className="error" role="alert">{error} You can fill in the fields below manually.</p>}
    {preview&&<section className="import-preview" aria-label="Import review"><h4>Review {preview.evidence.brand} · {preview.evidence.mpn}</h4>
      <p className="hint">Fetched {new Date(preview.evidence.retrieved_at).toLocaleString()} · English · Icecat ID {preview.evidence.product_id}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={`Imported specifications for ${preview.evidence.brand} ${preview.evidence.mpn}`}><table><thead><tr><th>Specification</th><th>Icecat proposes</th><th>Your current entry</th></tr></thead><tbody>{specKeys.map(key=>{
        const field=preview.evidence.fields.find(f=>f.field===key)
        return <tr key={key}><th scope="row">{specLabels[key]}</th><td>{field?.normalized||'Unknown'}</td><td>{preview.before[key]||'Unknown'}
          {sameProduct(preview.before,preview.evidence)&&(preview.before[key]||'')!==(field?.normalized||'')&&<label className="check"><input type="checkbox" checked={keep.includes(key)}
            onChange={e=>setKeep(current=>e.target.checked?[...current,key]:current.filter(k=>k!==key))}/>Keep my entry</label>}</td></tr>
      })}</tbody></table></div>
      {preview.evidence.issues.map(issue=><p className="hint" key={issue}>{issue}</p>)}
      {!sameProduct(preview.before,preview.evidence)&&<p className="notice">Applying a different product replaces its specifications and clears seller costs, compatibility, and battery-runtime evidence. Your notes remain.</p>}
      <p>Apply to the editable draft, complete missing details, then use “Confirm reviewed laptop.” Your workspace is saved only when you click Save.</p>
      {stale&&<p role="alert" className="notice">The draft changed while this preview was open. Fetch again to review those changes together.</p>}
      <div className="button-row"><button type="button" className="primary" disabled={!!stale} onClick={()=>{
        onApply(preview.before,applyImport(preview.before,preview.evidence,keep));setPreview(null);requestId.current=null
      }}>Apply to draft</button><button type="button" onClick={()=>setPreview(null)}>Discard preview</button></div>
    </section>}
    <p className="hint">Only Icecat is fetched. Other product links can be references for manual entry. Save the workspace to keep your reviewed specifications and source details. Unsaved imports older than 30 days must be fetched again before saving.</p>
  </details>
}
export function SourceEvidence({draft}:{draft:LaptopDraft}) {
  const source=draft.evidence
  if(!source)return null
  return <details className="source-evidence"><summary>Imported source and your corrections</summary>
    <p><a href={source.source_url} target="_blank" rel="noreferrer">Open Icecat · {source.brand} · {source.mpn}</a></p>
    <p className="hint">Retrieved {new Date(source.retrieved_at).toLocaleString()} · {source.language} · Mapping {source.mapper_version}. Source update date unavailable.</p>
    <div className="table-scroll" role="region" tabIndex={0} aria-label={`Source evidence for ${source.brand} ${source.mpn}`}><table><thead><tr><th>Field</th><th>Source value</th><th>Imported value</th><th>Your value</th></tr></thead><tbody>{source.fields.map(field=>
      <tr key={field.field}><th scope="row">{specLabels[field.field]}</th><td>{field.raw} {field.unit}</td><td>{field.normalized}</td><td>{draft[field.field]||'Unknown'}{draft[field.field]!==field.normalized?' · corrected by you':''}</td></tr>)}</tbody></table></div>
    {source.issues.map(issue=><p key={issue} className="hint">{issue}</p>)}
    <p className="hint">Specifications attributed to Open Icecat. Imported data is evidence for this configuration, not a measured performance guarantee.</p>
  </details>
}
