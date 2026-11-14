import test,{afterEach} from 'node:test'
import assert from 'node:assert/strict'
import {downloadSavedExport} from '../src/exportDownload.ts'
import {setSessionContext,sessionContextVersion} from '../src/api.ts'
const originals={fetch:globalThis.fetch,document:globalThis.document,window:globalThis.window,create:URL.createObjectURL,revoke:URL.revokeObjectURL}
afterEach(()=>{globalThis.fetch=originals.fetch;globalThis.document=originals.document;globalThis.window=originals.window;URL.createObjectURL=originals.create;URL.revokeObjectURL=originals.revoke;setSessionContext(null)})
function browser(response) {
  const events=[],link={href:'',download:'',click(){events.push('download')},remove(){events.push('remove')}}
  globalThis.fetch=async(path,options)=>{assert.equal(path,'/api/v1/account/export');assert.equal(options.cache,'no-store');return response}
  globalThis.window={dispatchEvent(event){events.push(event.type)}}
  globalThis.document={createElement(){return link},body:{appendChild(){events.push('append')}}}
  URL.createObjectURL=blob=>{assert.equal(blob.type,'application/json');events.push('blob');return 'blob:test'}
  URL.revokeObjectURL=()=>{}
  return {events,link}
}
test('downloads saved data only after a successful response',async()=>{
  const b=browser(Response.json({format:'purchase-decision-workspace',workspaces:[]}))
  await downloadSavedExport(new AbortController().signal,()=>true)
  assert.deepEqual(b.events,['blob','append','download','remove'])
  assert.equal(b.link.download,'purchase-decision-workspace-export.json')
})
test('account changes, unmounts or cancellation prevent late downloads',async()=>{
  for (const cancelled of [true,false]) {
    const b=browser(Response.json({workspaces:[]})),controller=new AbortController()
    if(cancelled)controller.abort()
    await downloadSavedExport(controller.signal,()=>false)
    assert.deepEqual(b.events,[])
  }
})
test('errors and non-JSON responses do not become downloads',async()=>{
  for (const response of [Response.json({code:'export_changed',message:'Retry export'},{status:409}),new Response('<html>error</html>')]) {
    const b=browser(response)
    await assert.rejects(downloadSavedExport(new AbortController().signal,()=>true))
    assert.deepEqual(b.events,[])
  }
})
test('unauthorized requests refresh account state without creating a file',async()=>{
  const b=browser(Response.json({code:'session_required',message:'Sign in'},{status:401}))
  await assert.rejects(downloadSavedExport(new AbortController().signal,()=>true))
  assert.deepEqual(b.events,['pdw-auth-required'])
})
test('same-session polling preserves its version; switching or signing out changes it',()=>{
  setSessionContext('session-a');const a=sessionContextVersion()
  setSessionContext('session-a');assert.equal(sessionContextVersion(),a)
  setSessionContext('session-b');assert.notEqual(sessionContextVersion(),a)
  const b=sessionContextVersion();setSessionContext(null);assert.notEqual(sessionContextVersion(),b)
})
