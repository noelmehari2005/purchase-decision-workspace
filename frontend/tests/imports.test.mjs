import test from 'node:test'
import assert from 'node:assert/strict'
import {applyImport,retainedCorrections} from '../src/imports.ts'
import {newLaptop,evaluationInput} from '../src/model.ts'
const evidence={receipt_id:'receipt',provider:'Open Icecat',product_id:'123',brand:'Example',mpn:'ABC#US',source_url:'https://icecat.biz/en/p.cgi?product_id=123',retrieved_at:'2026-11-13T00:00:00Z',language:'EN',source_updated_at:null,mapper_version:'1.0.0',issues:[],fields:[
  {field:'name',raw:'Example laptop',normalized:'Example laptop',unit:'',feature_id:''},
  {field:'configuration',raw:'ABC#US',normalized:'Example · ABC#US',unit:'',feature_id:''},
  {field:'ram',raw:'16',normalized:'16',unit:'GB',feature_id:'11381'}]}
test('applying an import is only an unconfirmed draft; no invented values or stale seller costs',()=>{
  const before={...newLaptop('a'),ram:'32',storage:'512',price:'800',compatible:'yes',battery:'300',notes:'My question'}
  const after=applyImport(before,evidence,[])
  assert.equal(before.ram,'32');assert.equal(after.ram,'16');assert.equal(after.storage,'');assert.equal(after.price,'')
  assert.equal(after.compatible,'unknown');assert.equal(after.battery,'');assert.equal(after.notes,'My question')
  assert.equal(after.evidence.product_id,'123')
})
test('same-product refresh preserves manual corrections and cost evidence unless user selects incoming',()=>{
  const original=applyImport(newLaptop('a'),evidence,[])
  const corrected={...original,ram:'24',display:'My display',price:'900',compatible:'yes'}
  const incoming={...evidence,fields:evidence.fields.filter(f=>f.field!=='ram')}
  const keep=retainedCorrections(corrected,incoming)
  assert.deepEqual(keep,['ram','display'])
  const after=applyImport(corrected,incoming,keep)
  assert.equal(after.ram,'24');assert.equal(after.display,'My display');assert.equal(after.price,'900');assert.equal(after.compatible,'yes')
  assert.equal(applyImport(corrected,incoming,[]).ram,'')
})
test('replacing product clears old specs while preserving the baseline identity',()=>{
  const original=applyImport(newLaptop('current',true),evidence,[])
  const next=applyImport({...original,ram:'24'},{...evidence,product_id:'456',fields:evidence.fields.filter(f=>f.field!=='ram')},['ram'])
  assert.equal(next.ram,'');assert.equal(next.current,true);assert.equal(next.id,'current');assert.equal(next.price,'0')
})
