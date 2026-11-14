import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync,mkdirSync,writeFileSync,unlinkSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import {randomUUID} from 'node:crypto'
import ts from 'typescript'
import {createElement} from 'react'
import {renderToStaticMarkup} from 'react-dom/server'

// Render the actual component with synthetic props; no test identity route is added.
const folder=new URL('../test-results/',import.meta.url)
mkdirSync(folder,{recursive:true})
const output=new URL(`lifecycle-${randomUUID()}.mjs`,folder)
const source=readFileSync(new URL('../src/AccountLifecycle.tsx',import.meta.url),'utf8')
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText
writeFileSync(output,compiled.replace("from './api'","from '../src/api.ts'"))
let AccountLifecycle
try {({AccountLifecycle}=await import(output.href))} finally {unlinkSync(fileURLToPath(output))}
const session={mode:'auth0',configured:true,authenticated:true,verified:true,account_state:'pending_deletion',delete_after:2000000000,can_restore:true,notification_status:'queued'}
const render=status=>renderToStaticMarkup(createElement(AccountLifecycle,{status,onClosed:()=>{}}))
test('recovery view requires explicit restoration and reports queued email honestly',()=>{
  const html=render(session)
  assert.match(html,/Restore account/);assert.match(html,/Signing in does not cancel deletion/)
  assert.match(html,/Queued; delivery not confirmed/);assert.doesNotMatch(html,/Start account deletion/)
})
test('closed recovery window has no restore action',()=>{
  const html=render({...session,can_restore:false})
  assert.match(html,/recovery window has ended/);assert.doesNotMatch(html,/>Restore account</)
})
test('active-account deletion starts disabled and explains missing email delivery',()=>{
  const html=render({...session,account_state:'active',notification_delivery_configured:false})
  assert.match(html,/DELETE MY ACCOUNT/);assert.match(html,/disabled=""/)
  assert.match(html,/Email delivery is not configured/);assert.match(html,/30-day recovery window/)
})
