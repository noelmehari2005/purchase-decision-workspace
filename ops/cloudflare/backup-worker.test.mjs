import test from 'node:test'
import assert from 'node:assert/strict'
import {createHmac,webcrypto} from 'node:crypto'
import worker,{triggerBackup,reportBackup} from './backup-worker.mjs'
if(!globalThis.crypto)globalThis.crypto=webcrypto
const ping='https://hc-ping.com/11111111-2222-3333-4444-555555555555'
const env={PDW_BACKUP_SCHEDULE_ENABLED:'1',PDW_API_ORIGIN:'https://fixture.onrender.com',
  PDW_BACKUP_SIGNING_SECRET:'a'.repeat(64),PDW_BACKUP_MONITOR_PING_URL:ping}
const success={status:'ok',mode:'backup',uploaded:true,writer_rotation_due:false}

test('disabled schedules and public requests cannot run backups',async()=>{
  assert.equal((await triggerBackup({}, {fetchImpl:()=>assert.fail('disabled')})).status,'disabled')
  assert.equal(worker.fetch().status,404)
})
test('separate path and key sign exactly one backup request without credentials in logs/body',async()=>{
  const calls=[]
  const result=await triggerBackup(env,{clock:()=>1795040000000,nonce:()=>'b'.repeat(32),fetchImpl:async(url,options)=>{
    calls.push({url,options});return Response.json(calls.length===1?{status:'ok'}:{...success,PRIVATE:'do not forward'})
  }})
  assert.deepEqual(result,success);assert.equal(calls[1].url,env.PDW_API_ORIGIN+'/api/v1/backups/run')
  assert.equal(calls[1].options.headers['X-PDW-Signature'],createHmac('sha256',env.PDW_BACKUP_SIGNING_SECRET)
    .update(`POST\n/api/v1/backups/run\n1795040000\n${'b'.repeat(32)}`).digest('hex'))
  assert.equal(calls[1].options.body,undefined);assert.equal(calls[1].options.redirect,'manual')
  assert.ok(!JSON.stringify(result).includes('PRIVATE'))
})
test('unsafe origin missing monitor or bad secret fails before network',async()=>{
  for(const change of [{PDW_API_ORIGIN:'https://evil.invalid'},{PDW_BACKUP_MONITOR_PING_URL:''},
    {PDW_BACKUP_MONITOR_PING_URL:ping+'?secret=PRIVATE'},{PDW_BACKUP_SIGNING_SECRET:'bad'}])
    await assert.rejects(triggerBackup({...env,...change},{fetchImpl:()=>assert.fail('invalid config')}))
})
test('redirects provider errors and false fresh-success are redacted failures',async()=>{
  for(const payload of [{status:'ok',mode:'backup',uploaded:false}, {status:'ok',mode:'check',uploaded:true},
    {status:'ok',mode:'backup',uploaded:true,writer_rotation_due:true}]) {
    let count=0
    await assert.rejects(triggerBackup(env,{fetchImpl:async()=>Response.json(++count===1?{status:'ok'}:payload)}),/Backup was not confirmed/)
  }
  for(const status of [302,503])
    await assert.rejects(triggerBackup(env,{fetchImpl:async()=>new Response('PRIVATE',{status})}),error=>!error.message.includes('PRIVATE'))
})
test('only a fresh upload with adequate credential lifetime emits an empty heartbeat',async()=>{
  for(const result of [{status:'busy'}, {status:'already_attempted'}, {status:'disabled'},
    {...success,status:'attention',writer_rotation_due:true},{...success,uploaded:false}])
    assert.deepEqual(await reportBackup(env,result,{fetchImpl:()=>assert.fail('false heartbeat')}),{monitor:'not_reported'})
  const calls=[]
  assert.deepEqual(await reportBackup(env,success,{fetchImpl:async(url,options)=>{
    calls.push({url,options});return new Response('OK')
  }}),{monitor:'accepted'})
  assert.equal(calls[0].url,ping);assert.equal(calls[0].options.body,undefined);assert.equal(calls[0].options.headers,undefined)
})
test('heartbeat failure never exposes the secret destination',async()=>{
  await assert.rejects(reportBackup(env,success,{fetchImpl:()=>{throw new Error('PRIVATE '+ping)}}),
    error=>!error.message.includes(ping)&&!error.message.includes('PRIVATE'))
})
