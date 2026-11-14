import test from 'node:test'
import assert from 'node:assert/strict'
import {privateAccess,sessionDeadline,workspaceIdentity,requiresSignIn} from '../src/session.ts'
const session={mode:'auth0',configured:true,authenticated:true,verified:true,
  user:{id:'owner-a',email:'a@example.com'},csrf:'session-a',idle_until:3700,absolute_until:86500}

test('only a verified authenticated identity can render private workspaces',()=>{
  assert.equal(privateAccess(session),true)
  for(const state of [null,{...session,authenticated:false},{...session,verified:false},{...session,verified:undefined},{...session,user:undefined}])
    assert.equal(privateAccess(state),false)
})
test('the earlier idle or absolute deadline closes the private view',()=>{
  assert.equal(sessionDeadline(session),3700000)
  assert.equal(sessionDeadline({...session,idle_until:90000}),86500000)
})
test('missing or nonfinite session deadlines fail closed',()=>{
  for(const state of [{...session,idle_until:undefined},{...session,absolute_until:NaN},{...session,idle_until:Infinity}])
    assert.equal(sessionDeadline(state),0)
})
test('signout or account changes produce a fresh workspace component identity',()=>{
  assert.notEqual(workspaceIdentity(session),workspaceIdentity({...session,authenticated:false}))
  assert.notEqual(workspaceIdentity(session),workspaceIdentity({...session,user:{id:'owner-b',email:'b@example.com'}}))
  assert.notEqual(workspaceIdentity(session),workspaceIdentity({...session,csrf:'new-login-session'}))
})
test('ordinary session checks preserve the same workspace identity',()=>{
  assert.equal(workspaceIdentity(session),workspaceIdentity({...session,idle_until:3800}))
  assert.equal(workspaceIdentity({...session,verified:false}),'demo')
  assert.equal(workspaceIdentity({mode:'local',authenticated:false,configured:false}),'local')
})

test('expired or absent sessions offer sign-in while outages do not imply configured auth',()=>{
  for (const code of ['session_required','session_expired','session_revoked','fresh_auth_required']) assert.equal(requiresSignIn(code),true)
  for (const code of ['identity_unavailable','auth_unconfigured','storage_unavailable','']) assert.equal(requiresSignIn(code),false)
})
