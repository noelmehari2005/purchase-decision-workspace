import type {LaptopDraft} from './model.ts'
export type SpecKey = 'name'|'configuration'|'cpu'|'os'|'ram'|'storage'|'weight'|'display'|'maxRam'|'batteryWh'
export interface SourceField {field:SpecKey; feature_id:string; raw:string; unit:string; normalized:string}
export interface ImportEvidence {
  receipt_id:string; provider:'Open Icecat'; product_id:string; brand:string; mpn:string; source_url:string;
  retrieved_at:string; language:'EN'; source_updated_at:null; mapper_version:'1.0.0'; fields:SourceField[]; issues:string[];
}
export const specLabels:Record<SpecKey,string> = {name:'Product name',configuration:'Configuration',cpu:'CPU',os:'Operating system',ram:'Installed RAM (GB)',storage:'Storage (GB)',weight:'Weight (g)',display:'Display',maxRam:'Maximum RAM (GB)',batteryWh:'Battery capacity (Wh)'}
export const specKeys = Object.keys(specLabels) as SpecKey[]
export function sameProduct(d:LaptopDraft,e:ImportEvidence) {return d.evidence?.product_id===e.product_id}
export function retainedCorrections(d:LaptopDraft,e:ImportEvidence):SpecKey[] {
  if (!sameProduct(d,e)) return []
  const old=new Map(d.evidence!.fields.map(f=>[f.field,f.normalized]))
  return specKeys.filter(key=>(d[key]||'')!==(old.get(key)||''))
}
export function applyImport(d:LaptopDraft,e:ImportEvidence,keep:SpecKey[]):LaptopDraft {
  const refresh=sameProduct(d,e), next={...d}
  for (const key of specKeys) next[key]=refresh&&keep.includes(key)?d[key]||'':''
  for (const field of e.fields) if (!keep.includes(field.field)||!refresh) next[field.field]=field.normalized
  if (!refresh) {
    next.compatible='unknown';next.battery='';next.batteryContext='';next.price=d.current?'0':'';next.tax=d.current?'0':'';
    next.shipping=d.current?'0':'';next.other='0';next.provisional='';next.costMode='components'
  }
  next.source=e.source_url;next.evidence=e
  return next
}
