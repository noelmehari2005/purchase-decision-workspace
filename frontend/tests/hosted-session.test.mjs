import test from 'node:test'
import assert from 'node:assert/strict'
import {readHostedSession,writeHostedSession} from '../src/hostedSession.ts'

const scope={hosted:true,apiOrigin:'https://api.onrender.com',domain:'example.auth0.com',
  clientId:'spa',audience:'https://api',returnTo:'https://owner.github.io/repo/'}
const token='a'.repeat(43)
function tab() {
  const entries=new Map()
  return {entries,storage:()=>({getItem:key=>entries.get(key)??null,
    setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key)})}
}
test('same-tab reload can retrieve the opaque credential; a separate tab starts signed out',()=>{
  const first=tab(),second=tab()
  writeHostedSession(scope,first.storage,token)
  assert.equal(readHostedSession(scope,first.storage),token)
  assert.equal(readHostedSession(scope,second.storage),null)
  assert.equal(first.entries.size,1)
  // No identity/profile, CSRF data or timestamps are persisted with the token.
  assert.deepEqual([...first.entries.values()],[token])
})
test('logout or a rejected session removes the persisted credential',()=>{
  const current=tab()
  writeHostedSession(scope,current.storage,token)
  writeHostedSession(scope,current.storage,null)
  assert.equal(readHostedSession(scope,current.storage),null)
  assert.equal(current.entries.size,0)
})
test('a new provider callback cannot reopen an earlier identity, including a failed callback',()=>{
  for(const search of ['?code=fictional&state=fixture','?error=access_denied&state=fixture']) {
    const current=tab()
    writeHostedSession(scope,current.storage,token)
    assert.equal(readHostedSession(scope,current.storage,search),null)
    assert.equal(current.entries.size,0)
  }
})
test('other deployments cannot accidentally reuse a saved credential',()=>{
  const current=tab()
  writeHostedSession(scope,current.storage,token)
  for(const field of ['apiOrigin','domain','clientId','audience','returnTo'])
    assert.equal(readHostedSession({...scope,[field]:scope[field]+'other'},current.storage),null)
  assert.equal(readHostedSession({...scope,hosted:false},current.storage),null)
  writeHostedSession({...scope,hosted:false},current.storage,null)
  assert.equal(readHostedSession(scope,current.storage),token)
})
test('provider JWTs and malformed credentials are not retained',()=>{
  const current=tab()
  writeHostedSession(scope,current.storage,token)
  const name=[...current.entries.keys()][0]
  for(const invalid of ['', 'header.payload.signature','x'.repeat(257),'bad token']) {
    current.entries.set(name,invalid)
    assert.equal(readHostedSession(scope,current.storage),null)
    assert.equal(current.entries.size,0)
    writeHostedSession(scope,current.storage,invalid)
    assert.equal(current.entries.size,0)
  }
})
test('blocked or exhausted tab storage falls back without breaking sign-in',()=>{
  const denied=()=>{throw new Error('Storage denied')}
  assert.equal(readHostedSession(scope,denied),null)
  assert.doesNotThrow(()=>writeHostedSession(scope,denied,token))
  const full=()=>({getItem:()=>null,setItem:()=>{throw new Error('Quota exceeded')},removeItem:()=>{}})
  assert.doesNotThrow(()=>writeHostedSession(scope,full,token))
  const current=tab()
  writeHostedSession(scope,current.storage,token)
  const failedWrite=()=>({...current.storage(),setItem:()=>{throw new Error('Quota exceeded')}})
  writeHostedSession(scope,failedWrite,'b'.repeat(43))
  assert.equal(readHostedSession(scope,current.storage),null)
})
