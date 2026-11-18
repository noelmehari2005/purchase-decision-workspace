import test,{afterEach} from 'node:test'
import assert from 'node:assert/strict'
import {storageRequest,StorageRequestError} from '../src/api.ts'

const originals={fetch:globalThis.fetch,window:globalThis.window}
afterEach(()=>{globalThis.fetch=originals.fetch;globalThis.window=originals.window})

test('session rejection does not trigger another session-refresh event; private requests still do',async()=>{
  for(const [path,expected] of [['/auth/session',[]],['/decisions',['pdw-auth-required']]]) {
    const events=[]
    globalThis.window={dispatchEvent:event=>events.push(event.type)}
    globalThis.fetch=async()=>Response.json({code:'session_expired',message:'Sign in again.'},{status:401})
    await assert.rejects(storageRequest(path),error=>error instanceof StorageRequestError && error.code==='session_expired')
    assert.deepEqual(events,expected)
  }
})
